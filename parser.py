"""
Module de parsing des noms d'annonces
Extrait angle marketing, créateur et format avec approche multi-niveaux
"""
import re
import json
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from config import BrandConfig, ParsingConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ParsedEntity:
    """Résultat du parsing d'une annonce"""
    angle: Optional[str] = None
    creator_gender: Optional[str] = None
    creator_age: Optional[int] = None
    format_type: Optional[str] = None
    parse_source: str = "unknown"  # regex, fuzzy, llm, failed
    confidence: float = 0.0
    ambiguity_reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "angle": self.angle,
            "creator_gender": self.creator_gender,
            "creator_age": self.creator_age,
            "format": self.format_type,
            "parse_source": self.parse_source,
            "confidence": self.confidence,
            "ambiguity_reason": self.ambiguity_reason
        }


class AdNameParser:
    """Parse les noms d'annonces avec approche multi-tiers"""
    
    def __init__(self, brand_config: BrandConfig = None):
        self.config = brand_config or BrandConfig(brand_id="default", account_ids=[])
        self.official_pattern = re.compile(ParsingConfig.OFFICIAL_SCHEMA, re.IGNORECASE)
        
        # Compiler les patterns de créateurs
        self.creator_patterns = {}
        for key, pattern in self.config.creator_patterns.items():
            self.creator_patterns[key] = re.compile(pattern, re.IGNORECASE)
    
    def parse(self, ad_name: str) -> ParsedEntity:
        """
        Parse un nom d'annonce avec approche multi-tiers
        
        Args:
            ad_name: Nom de l'annonce à parser
        
        Returns:
            ParsedEntity avec les informations extraites
        """
        # Tier 1: Regex strict sur nomenclature officielle
        result = self._parse_regex(ad_name)
        if result.confidence >= 0.9:
            return result
        
        # Tier 2: Fuzzy matching avec dictionnaires
        result = self._parse_fuzzy(ad_name)
        if result.confidence >= 0.7:
            return result
        
        # Tier 3: LLM (si activé)
        if ParsingConfig.ENABLE_LLM and ParsingConfig.OPENAI_API_KEY:
            result = self._parse_llm(ad_name)
            if result.confidence >= ParsingConfig.LLM_CONFIDENCE_THRESHOLD:
                return result
        
        # Échec du parsing
        return ParsedEntity(
            parse_source="failed",
            confidence=0.0,
            ambiguity_reason=f"Impossible de parser: {ad_name}"
        )
    
    def _parse_regex(self, ad_name: str) -> ParsedEntity:
        """
        Tier 1: Parse avec regex strict
        Format attendu: angle_XXX|creador_XXX|tipo_XXX
        """
        match = self.official_pattern.match(ad_name)
        if not match:
            return ParsedEntity(parse_source="regex", confidence=0.0)
        
        groups = match.groupdict()
        
        # Extraire l'angle
        angle_raw = groups.get("angle", "").lower()
        angle = self._normalize_angle(angle_raw)
        
        # Extraire créateur
        creator_raw = groups.get("creator", "")
        gender, age = self._extract_creator_info(creator_raw)
        
        # Extraire format
        format_raw = groups.get("format", "").lower()
        format_type = self._normalize_format(format_raw)
        
        # Calculer la confiance
        confidence = 1.0
        if not angle:
            confidence -= 0.3
        if not gender:
            confidence -= 0.2
        if not format_type:
            confidence -= 0.2
        
        return ParsedEntity(
            angle=angle,
            creator_gender=gender,
            creator_age=age,
            format_type=format_type,
            parse_source="regex",
            confidence=confidence
        )
    
    def _parse_fuzzy(self, ad_name: str) -> ParsedEntity:
        """
        Tier 2: Parse avec dictionnaires et patterns flexibles
        """
        ad_lower = ad_name.lower()
        
        # Chercher l'angle
        angle = None
        for angle_key, keywords in self.config.angle_keywords.items():
            for keyword in keywords:
                if keyword.lower() in ad_lower:
                    angle = angle_key
                    break
            if angle:
                break
        
        # Chercher le format
        format_type = None
        for format_key, keywords in self.config.format_keywords.items():
            for keyword in keywords:
                if keyword.lower() in ad_lower:
                    format_type = format_key
                    break
            if format_type:
                break
        
        # Chercher créateur avec patterns
        gender = None
        age = None
        
        for pattern_key, pattern in self.creator_patterns.items():
            match = pattern.search(ad_name)
            if match:
                if "male" in pattern_key:
                    gender = "M"
                elif "female" in pattern_key:
                    gender = "F"
                
                # Extraire l'âge si présent dans le match
                groups = match.groups()
                if groups:
                    try:
                        age = int(groups[-1])  # Dernier groupe est souvent l'âge
                    except (ValueError, IndexError):
                        pass
                
                if gender:
                    break
        
        # Calculer la confiance
        confidence = 0.3  # Base fuzzy
        if angle:
            confidence += 0.3
        if format_type:
            confidence += 0.2
        if gender:
            confidence += 0.2
        
        ambiguity = []
        if not angle:
            ambiguity.append("angle non détecté")
        if not format_type:
            ambiguity.append("format non détecté")
        if not gender:
            ambiguity.append("créateur non détecté")
        
        return ParsedEntity(
            angle=angle,
            creator_gender=gender,
            creator_age=age,
            format_type=format_type,
            parse_source="fuzzy",
            confidence=confidence,
            ambiguity_reason=", ".join(ambiguity) if ambiguity else None
        )
    
    def _parse_llm(self, ad_name: str) -> ParsedEntity:
        """
        Tier 3: Parse avec LLM (OpenAI)
        """
        try:
            import openai
            
            client = openai.OpenAI(api_key=ParsingConfig.OPENAI_API_KEY)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at parsing Facebook ad names."},
                    {"role": "user", "content": ParsingConfig.LLM_PROMPT.format(ad_name=ad_name)}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            # Parser la réponse JSON
            result_text = response.choices[0].message.content
            result_json = json.loads(result_text)
            
            return ParsedEntity(
                angle=result_json.get("angle"),
                creator_gender=result_json.get("creator_gender"),
                creator_age=result_json.get("creator_age"),
                format_type=result_json.get("format"),
                parse_source="llm",
                confidence=result_json.get("confidence", 0.5)
            )
            
        except Exception as e:
            logger.error(f"Erreur LLM parsing: {e}")
            return ParsedEntity(
                parse_source="llm",
                confidence=0.0,
                ambiguity_reason=f"Erreur LLM: {str(e)}"
            )
    
    def _normalize_angle(self, angle_raw: str) -> Optional[str]:
        """Normalise l'angle vers une valeur standard"""
        angle_lower = angle_raw.lower().strip()
        
        # Chercher dans les mots-clés
        for angle_key, keywords in self.config.angle_keywords.items():
            if angle_lower in [k.lower() for k in keywords]:
                return angle_key
            # Vérifier si l'angle contient un mot-clé
            for keyword in keywords:
                if keyword.lower() in angle_lower:
                    return angle_key
        
        # Si pas trouvé mais non vide, garder tel quel
        if angle_lower and angle_lower != "angulo":
            return angle_lower
        
        return None
    
    def _normalize_format(self, format_raw: str) -> Optional[str]:
        """Normalise le format vers une valeur standard"""
        format_lower = format_raw.lower().strip()
        
        # Chercher dans les mots-clés
        for format_key, keywords in self.config.format_keywords.items():
            if format_lower in [k.lower() for k in keywords]:
                return format_key
            # Vérifier si le format contient un mot-clé
            for keyword in keywords:
                if keyword.lower() in format_lower:
                    return format_key
        
        # Si pas trouvé mais non vide, garder tel quel
        if format_lower and format_lower != "tipo":
            return format_lower
        
        return None
    
    def _extract_creator_info(self, creator_raw: str) -> Tuple[Optional[str], Optional[int]]:
        """Extrait le genre et l'âge du créateur"""
        if not creator_raw:
            return None, None
        
        creator_lower = creator_raw.lower()
        
        # Détection du genre
        gender = None
        if any(x in creator_lower for x in ["hombre", "homme", "man", "m_", "h_"]):
            gender = "M"
        elif any(x in creator_lower for x in ["mujer", "femme", "woman", "f_", "w_"]):
            gender = "F"
        
        # Extraction de l'âge
        age = None
        age_match = re.search(r'\d{2}', creator_raw)
        if age_match:
            try:
                age = int(age_match.group())
                if age < 10 or age > 99:  # Validation basique
                    age = None
            except ValueError:
                pass
        
        return gender, age


def test_parser():
    """Test le parser avec différents exemples"""
    parser = AdNameParser()
    
    test_cases = [
        # Nomenclature officielle
        "inflamacion|Hombre25|video",
        "digestion|Mujer_30|imagen",
        "energia|Carlos25|reel",
        
        # Variations
        "Inflamación - Ana 28 - Video FB",
        "DIGESTION_M30_IMG",
        "energia fatiga woman35 carousel",
        
        # Cas ambigus
        "Promo verano 2024",
        "Test_123",
        "Nueva campaña digestiva"
    ]
    
    print("🧪 Test du parser de noms d'annonces\n")
    print("-" * 80)
    
    for ad_name in test_cases:
        result = parser.parse(ad_name)
        print(f"\n📝 Nom: {ad_name}")
        print(f"   Angle: {result.angle or '❌'}")
        print(f"   Créateur: {result.creator_gender or '?'}{result.creator_age or ''}")
        print(f"   Format: {result.format_type or '❌'}")
        print(f"   Source: {result.parse_source} (confiance: {result.confidence:.1%})")
        if result.ambiguity_reason:
            print(f"   ⚠️ {result.ambiguity_reason}")


if __name__ == "__main__":
    test_parser()