// =============== Nomenclature Parser v2 ===============
// Tolérant aux variantes, avec score de confiance et détection créateur robuste.
// ======================================================================

(function(){
  // --- Utils ---
  const rmAcc = s => (s||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,''); // strip accents (working copy)
  const toTitle = s => (s||'')
    .toLowerCase()
    .replace(/\s+/g,' ')
    .trim()
    .replace(/\b\w/g, c => c.toUpperCase());

  // --- NEW: alias explicites pour "créateurs" catégoriels
  const CREATOR_ALIASES = new Map([
    ['voz ia', 'Voz IA'],
    ['ai voice', 'Voz IA'],
    ['voz en off', 'Voz En Off'],
    ['equipo', 'Equipo'],
    ['marca', 'Marca'],
    ['estatico', 'Estático'],
    ['combinado', 'Combinado']
  ]);

  // Séparateurs considérés comme "structurels"
  const SEP = /\s*(?:\||[>]|[_]|—|–)\s*/g;
  const CODE_LIKE = /\b(?:AG\d+|0\d{3}[A-Z]?\w*|[A-Z]{1,3}\d{2,}S?\w*|SP\d{2,}|PD\d{2,}|[A-Z]{2,}\d{2,})\b/gi;

  const STOP_CREATOR = /\b(?:na|n\/a|none|s\/?d|general|voz ?ia|creador(?:a)? (?:ia|marca|equipo)|hombre|mujer|mujeres|hombres|varios creadores|organico|voz en off|fase|fase \d+|nuevo|nueva|iteracion|iteración|estatico|estático|video|imagen|img|carousel|carrusel|el|la|los|las|si|no|mas|más|top|top \d+|batch|batch \d+|test|prueba|copy|copia|ad|ad \d+|anuncio|campaña|campaign)\b/i;
  const NA_RE = /^(?:na|n\/a|none|s\/?d|general|-|—|_)?$/i;

  // Type
  const TYPE_RE_STRICT = /^(?:nuevo|new|it|iteracion|iteración|iteration)\b/i;
  const TYPE_RE_LOOSE  = /\b(?:nuevo|new|it|iteracion|iteración|iteration)\b/i;

  // Edad
  const AGE_RE = /\b(\d{2})\s*[-–]\s*(\d{2}\+?)\b/;

  // Hook / Version
  const HOOK_RE = /\b(?:hook?\s*\d+|h\d+)\b/gi;
  const V_RE = /\bv0*(\d+)(?:\s*-\s*\d+)?\b/i;           // V1 / V02
  const VH_RE = /\bv0*(\d+)h0*(\d+)\b/i;                // V1H2 / V01H02
  const H_COMPACT = /\bh(\d{2,})\b/i;                   // H123
  const H_RANGE = /\bh(\d+)\s*[-–]\s*(\d+)\b/i;         // H1-3

  // Mots à retirer du champ Angle (clutter méthodo/campagne)
  const ANGLE_NOISE = /\b(?:tc|am|cp|fase\s*\d+|video|vid|imagen|img|estatico|estático|carousel|carrusel|ig|ad\s*\d+|copia|promo(?:ciones)?)\b/gi;
  const V_PREFIX = /^\s*[ve]-\s*/i;

  // Formats (hint)
  function formatHint(s){
    if (/vid(?:eo)?/i.test(s)) return 'VIDEO';
    if (/(?:image|imagen|img|foto|estatico|estático)/i.test(s)) return 'IMAGE';
    if (/(?:carru?sel|carousel|ig)/i.test(s)) return 'CAROUSEL';
    return '';
  }

  // Lexique dynamique de créateurs (rempli depuis les données courantes)
  let KNOWN_CREATORS = new Map(); // name -> count

  function setKnownCreatorsFromAds(ads){
    KNOWN_CREATORS.clear();
    const add = (name)=> {
      if (!name) return;
      const key = toTitle(name);
      KNOWN_CREATORS.set(key, (KNOWN_CREATORS.get(key)||0) + 1);
    };
    // naïf mais efficace : prendre le 3e segment si type au 1er, + tous tokens ressemblant à "prénom/nom"
    for (const ad of ads||[]) {
      const raw = (ad.ad_name||'').trim();
      if (!raw) continue;

      // segmentation "light" façon parser
      const s0 = raw.replace(SEP, '/').replace(/\s{2,}/g,' ').trim();
      const parts = s0.split('/').map(x=>x.trim()).filter(Boolean);
      const p0 = rmAcc(parts[0]||'').toLowerCase();

      // 3e segment comme candidat créateur
      if (TYPE_RE_STRICT.test(p0) && parts[2] && !STOP_CREATOR.test(parts[2]) && !/\d/.test(parts[2])) {
        add(parts[2]);
      }

      // fallback : récolte de tokens "Prénom Nom"
      const caps = (raw.match(/\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)?\b/g) || []);
      caps.forEach(add);
    }
  }

  function creatorLikelihood(tok){
    if (!tok) return 0;
    const s = tok.trim();
    if (!s || STOP_CREATOR.test(s)) return 0;
    
    // Rejeter si contient des chiffres (sauf initiales comme "Daniel B.")
    if (/\d/.test(s) && !/^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+\s+[A-Z]\.$/.test(s)) return 0;
    
    // Rejeter les mots trop courts (sauf dans le lexique)
    const key = toTitle(s);
    if (s.length <= 2 && !KNOWN_CREATORS.has(key)) return 0;
    
    // Rejeter si c'est un mot commun espagnol/anglais
    const commonWords = /^(el|la|los|las|de|del|en|con|sin|por|para|sobre|desde|hasta|si|no|mas|más|muy|mucho|poco|todo|nada|algo|bien|mal|mejor|peor|grande|pequeño|nuevo|viejo|joven|bueno|malo|primero|ultimo|the|and|or|but|with|without|for|from|about|more|less|very|much|all|nothing|something|good|bad|new|old|young|first|last)$/i;
    if (commonWords.test(s)) return 0;
    
    // heuristique "nom propre" - Plus strict maintenant
    // Doit commencer par majuscule et avoir au moins 3 lettres
    const proper = /^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|(?:\s+[A-Z]\b))?$/.test(s);
    
    // Si pas un nom propre ET pas dans le lexique, rejeter
    if (!proper && !KNOWN_CREATORS.has(key)) return 0;
    
    let score = proper ? 0.4 : 0.2;
    
    // Bonus si dans le lexique ET vu plusieurs fois
    if (KNOWN_CREATORS.has(key)) {
      const c = KNOWN_CREATORS.get(key);
      if (c >= 2) score += 0.3; // Fort bonus si vu plusieurs fois
      else score += 0.1;
    }
    
    // pénalités pour tout en majuscules (sauf si court comme "MAX")
    if (s === s.toUpperCase() && s.length > 3 && !KNOWN_CREATORS.has(key)) score -= 0.3;
    
    return Math.max(0, Math.min(1, score));
  }

  function expandHCompact(s, acc){
    // H123 → H1,H2,H3
    const m = s.match(H_COMPACT);
    if (!m) return;
    const digits = m[1];
    digits.split('').forEach(d => acc.add(`H${parseInt(d,10)}`));
  }

  function expandHRange(s, acc){
    // H1-3 → H1,H2,H3
    const m = s.match(H_RANGE);
    if (!m) return;
    const a = parseInt(m[1],10), b = parseInt(m[2],10);
    if (isFinite(a) && isFinite(b) && b >= a && b - a <= 10) {
      for (let i=a; i<=b; i++) acc.add(`H${i}`);
    }
  }

  function parseHookBlock(all){
    const hooks = new Set();
    let v = null;

    // VxHy fusionnés
    const mvh = all.match(VH_RE);
    if (mvh) {
      const mm = VH_RE.exec(all);
      v = `V${parseInt(mm[1],10)}`;
      hooks.add(`H${parseInt(mm[2],10)}`);
    }

    // Vx isolé (si pas déjà capturé)
    if (!v) {
      const mv = all.match(/\bV0*\d+\b/i);
      if (mv) v = `V${parseInt(mv[0].slice(1),10)}`;
    }

    // H compact / range
    expandHCompact(all, hooks);
    expandHRange(all, hooks);

    // H classiques & Hook X
    (all.match(HOOK_RE)||[]).forEach(h => {
      const num = h.replace(/hook?/i,'H').replace(/[^\d]/g,'');
      if (num) hooks.add(`H${parseInt(num,10)}`);
    });

    // Listes "H1,2,3" / "H1 y 3"
    (all.match(/\bH\d+(?:\s*[,y]\s*\d+)+\b/gi)||[]).forEach(seq=>{
      const first = /H(\d+)/i.exec(seq)[1];
      hooks.add(`H${parseInt(first,10)}`);
      (seq.match(/\d+/g)||[]).slice(1).forEach(n => hooks.add(`H${parseInt(n,10)}`));
    });

    // Nettoyage et rendu
    const hList = [...hooks].sort((a,b)=>parseInt(a.slice(1))-parseInt(b.slice(1)));
    if (v && hList.length === 1) return `${v}${hList[0]}`;     // ex: V1H2
    if (v && hList.length > 1) return `${v}/${hList.join(',')}`;
    if (hList.length > 0) return hList.join(',');
    return v || '';
  }

  function cleanAngle(s){
    if (!s || NA_RE.test(s)) return '';
    // retire bruit méthodo
    let out = s.replace(ANGLE_NOISE,' ').replace(/\s{2,}/g,' ').trim();
    // gère v- / e-
    out = out.replace(V_PREFIX,'');
    // coupe listes très longues en gardant l'idée principale si besoin
    return toTitle(out);
  }

  function parseAdNameV2(raw, overrides){
    const res = { type:'—', angle:'', creator:'', age:'', hook:'', format_hint:'', confidence:0, field_confidence:{type:0,angle:0,creator:0,age:0,hook:0} };
    if (!raw) return res;
    
    // Apply overrides if provided
    if (overrides) {
        if (overrides.angle) res.angle = overrides.angle;
        if (overrides.creator) res.creator = overrides.creator;
        if (overrides.age) res.age = overrides.age;
        if (overrides.hook) res.hook = overrides.hook;
        if (overrides.type) res.type = overrides.type;
        res.confidence = 100; // Override always has full confidence
        res.field_confidence = {type:1,angle:1,creator:1,age:1,hook:1};
        return res;
    }

    // Copie de travail
    let s = String(raw);
    // indice format (pour dashboard)
    res.format_hint = formatHint(s);

    // purge codes isolés pour ne pas polluer
    s = s.replace(CODE_LIKE, ' ');
    // standardise séparateurs
    s = s.replace(SEP, '/').replace(/\s*\/\s*/g,'/').replace(/\s{2,}/g,' ').trim();

    const parts = s.split('/').map(p => p.trim()).filter(Boolean);
    const all = parts.join(' / ');
    const allNoAcc = rmAcc(all).toLowerCase();

    // === TYPE ===
    const p0 = rmAcc(parts[0]||'').toLowerCase();
    if (TYPE_RE_STRICT.test(p0)) {
      res.type = /(?:^|\/)\s*(?:it|iteracion|iteración|iteration)\b/i.test(parts[0]) ? 'Iteración' : 'Nuevo';
      res.confidence += (res.field_confidence.type = 40);
    } else {
      const m = allNoAcc.match(TYPE_RE_LOOSE);
      if (m) {
        res.type = /it|iteracion|iteración|iteration/.test(m[0]) ? 'Iteración' : 'Nuevo';
        res.confidence += (res.field_confidence.type = 20);
      }
    }

    // === ANGLE ===
    let angle = '';
    if (parts[1] && !NA_RE.test(parts[1])) angle = cleanAngle(parts[1]);
    if (!angle) {
      // fallback "v-xxx" ou "e-xxx"
      const m = all.match(/\b[ve]-\s*([a-záéíóúñ ]{3,})\b/i);
      if (m) angle = cleanAngle(m[1]);
    }
    if (angle) {
      const direct = !!(parts[1] && cleanAngle(parts[1]));
      res.angle = angle;
      res.confidence += (res.field_confidence.angle = direct ? 40 : 20);
    }

    // === CREATOR === (3e segment prioritaire)
    let creatorCand = (parts[2]||'').trim();
    let cScore = 0;
    
    // NEW: alias explicites (passe AVANT la stop-list)
    const aliasKey = rmAcc(creatorCand).toLowerCase();
    if (creatorCand && CREATOR_ALIASES.has(aliasKey)) {
      res.creator = CREATOR_ALIASES.get(aliasKey);
      res.confidence += (res.field_confidence.creator = 50);
    } else {
      if (creatorCand && !NA_RE.test(creatorCand)) {
        cScore = creatorLikelihood(creatorCand);
      }
      // fallback : chercher un Nom Propre crédible ailleurs si score trop bas
      if (cScore < 0.5) {
        const caps = (all.match(/\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|(?:\s+[A-Z]\b))?\b/g) || [])
          .map(toTitle)
          .filter(n => creatorLikelihood(n) >= 0.5);
        if (caps.length) {
          // prioriser ceux connus
          caps.sort((a,b)=>(KNOWN_CREATORS.get(b)||0)-(KNOWN_CREATORS.get(a)||0));
          creatorCand = caps[0];
          cScore = creatorLikelihood(creatorCand);
        }
      }
      if (cScore >= 0.5) {
        res.creator = toTitle(creatorCand);
        // 30 de base + bonus fréquentation (cap à 50 total champ)
        const base = 30;
        const bonus = Math.min(20, Math.max(0, (cScore-0.3)*100));
        res.confidence += (res.field_confidence.creator = base + bonus);
      }
    }

    // === AGE ===
    const ageM = all.match(AGE_RE);
    if (ageM) {
      res.age = `${ageM[1]}-${ageM[2]}`.replace(/\s+/g,'');
      res.confidence += (res.field_confidence.age = 10);
    }

    // === HOOK ===
    const hook = parseHookBlock(all);
    if (hook) {
      res.hook = hook.toUpperCase().replace(/\s+/g,'');
      // +5 si compact/range expand détecté
      const extra = (H_COMPACT.test(all) || H_RANGE.test(all)) ? 15 : 10;
      res.confidence += (res.field_confidence.hook = extra);
    }

    // clamp
    res.confidence = Math.min(100, res.confidence);
    return res;
  }

  // Expose dans la page ou pour Node.js
  const NOMEN_V2 = {
    parseAdName: parseAdNameV2,
    setKnownCreatorsFromAds
  };

  // Export pour navigateur
  if (typeof window !== 'undefined') {
    window.NOMEN_V2 = NOMEN_V2;
  }

  // Export pour Node.js
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = NOMEN_V2;
  }
})();