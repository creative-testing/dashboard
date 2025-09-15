// =============== Nomenclature Parser - SIMPLE (strict 5 segments) ===============
(function () {
  // --- utils ---
  const toTitle = s => (s || '').trim();
  const isNA = s => /^n\/a$/i.test((s || '').trim());

  // Normalise "N / A" (ou variations d'espaces/majuscules) -> "N/A"
  function normalizeNA(s) {
    return String(s || '').replace(/\bN\s*\/\s*A\b/gi, 'N/A');
  }

  // Protège les "N/A" pour ne pas être coupés par le split('/')
  function protectNA(s) {
    return String(s || '').replace(/N\/A/gi, '<<__NA__>>');
  }
  function unprotectNA(strOrArr) {
    const un = v => String(v || '').replace(/<<__NA__>>/g, 'N/A');
    return Array.isArray(strOrArr) ? strOrArr.map(un) : un(strOrArr);
  }

  /**
   * Split strict en 5 segments (Type / Angle / Creator / Age / Hook)
   * - Ne coupe jamais les "N/A"
   * - Cas legacy EXACTEMENT 6 segments: supprime le 5e (ancien format)
   * - Si <5: pad à N/A ; si >5: concatène le surplus dans le 5e (Hook)
   */
  function split5(raw) {
    if (!raw) return ['', '', '', '', ''];
    let s = String(raw).trim();

    // 1) normaliser "N / A" -> "N/A"
    s = normalizeNA(s);

    // 2) normaliser les espaces autour des slash
    s = s.replace(/\s*\/\s*/g, '/');

    // 3) protéger "N/A"
    s = protectNA(s);

    // 4) split
    let parts = s.split('/').map(p => p.trim());

    // 5) déprotéger
    parts = unprotectNA(parts);

    // 6) règle legacy: exactement 6 segments -> retirer le 5e
    if (parts.length === 6) {
      // supprime la 5e (index 4)
      parts.splice(4, 1); // il reste 5 segments: [0,1,2,3,5]
    }

    // 7) clamp à 5 segments
    if (parts.length < 5) {
      while (parts.length < 5) parts.push('N/A');
    } else if (parts.length > 5) {
      // cas très rare >6 dès l'entrée : garder 4 premiers, concaténer le reste en Hook
      const head = parts.slice(0, 4);
      const tail = parts.slice(4).join(' / ');
      parts = [...head, tail];
    }
    return parts;
  }

  // Normalisation minimale du TYPE
  function normalizeType(p0) {
    const t = (p0 || '').trim().toLowerCase();
    if (/^(it|iteracion|iteración|iteration)\b/.test(t)) return 'Iteración';
    if (/^(nuevo|new)\b/.test(t)) return 'Nuevo';
    return p0 || '—';
  }

  // Parser SIMPLE
  function parseAdNameSimple(raw, overrides) {
    const res = {
      type: '—', angle: '', creator: '', age: '', hook: '',
      format_hint: '', // laissé pour compat
      confidence: 0,
      field_confidence: { type: 0, angle: 0, creator: 0, age: 0, hook: 0 }
    };
    if (!raw) return res;

    // Priorité aux overrides (compat avec votre UI)
    if (overrides) {
      if (overrides.type)    res.type    = overrides.type;
      if (overrides.angle)   res.angle   = overrides.angle;
      if (overrides.creator) res.creator = overrides.creator;
      if (overrides.age)     res.age     = overrides.age;
      if (overrides.hook)    res.hook    = overrides.hook;
      res.confidence = 100;
      res.field_confidence = { type:1, angle:1, creator:1, age:1, hook:1 };
      return res;
    }

    const [p0, p1, p2, p3, p4] = split5(raw);

    res.type    = normalizeType(p0);
    res.angle   = isNA(p1) ? '' : toTitle(p1);
    res.creator = isNA(p2) ? '' : toTitle(p2);
    res.age     = isNA(p3) ? '' : toTitle(p3);
    res.hook    = isNA(p4) ? '' : toTitle(p4);

    // Confiance proportionnelle aux champs non vides (simple & transparent)
    const f = res.field_confidence;
    f.type    = res.type !== '—' ? 1 : 0;
    f.angle   = res.angle ? 1 : 0;
    f.creator = res.creator ? 1 : 0;
    f.age     = res.age ? 1 : 0;
    f.hook    = res.hook ? 1 : 0;
    res.confidence = (f.type + f.angle + f.creator + f.age + f.hook) * 20;

    return res;
  }

  // Compat : l'UI appelle setKnownCreatorsFromAds — ici c'est un no‑op
  function setKnownCreatorsFromAds() {}

  const NOMEN_V2 = { parseAdName: parseAdNameSimple, setKnownCreatorsFromAds };
  if (typeof window !== 'undefined') window.NOMEN_V2 = NOMEN_V2;
  if (typeof module !== 'undefined' && module.exports) module.exports = NOMEN_V2;
})();
