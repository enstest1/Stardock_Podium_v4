"""
Star Trek–aware text tweaks before Kokoro / misaki phonemization.

Kokoro has no SSML; cardinal readings of stardates (e.g. 871 → "eight hundred
seventy-one") and odd G2P for franchise terms are fixed by expanding stardates
to spoken digits and respelling select proper nouns.

XTTS and other engines should run the same :func:`normalize_trek_tts_text`
pipeline so species names stay consistent across backends.
"""

from __future__ import annotations

import re
from typing import List, Tuple

_DIGIT_WORDS = {
    '0': 'zero',
    '1': 'one',
    '2': 'two',
    '3': 'three',
    '4': 'four',
    '5': 'five',
    '6': 'six',
    '7': 'seven',
    '8': 'eight',
    '9': 'nine',
}


def _spell_digits(digits: str) -> str:
    return ' '.join(_DIGIT_WORDS[c] for c in digits if c in _DIGIT_WORDS)


# Longest-first regex replacements (species / franchise lexicon).
# Spellings tuned for English G2P: approximate screen pronunciations.
_LEXICON: List[Tuple[re.Pattern[str], str]] = [
    # --- Phrases (before single-word species that appear inside them) ---
    (re.compile(r'\bRomulan Free State\b', re.IGNORECASE), 'Rom-yoo-lun Free Stayt'),
    (re.compile(r'\bKlingon Defense Force\b', re.IGNORECASE), 'Kling-on Deh-fense Force'),
    (re.compile(r'\bCardassian Reconstruction Authority\b', re.IGNORECASE),
     'Car-dass-ee-un Ree-kun-struk-shun Aw-thor-ih-tee'),
    (re.compile(r'\bBajoran Militia\b', re.IGNORECASE), 'Bay-jor-un Mih-lish-uh'),
    (re.compile(r'\bFerengi Alliance\b', re.IGNORECASE), 'Feh-ren-jee Uh-ly-ence'),
    (re.compile(r'\bFerengi Commerce Authority\b', re.IGNORECASE),
     'Feh-ren-jee Kom-ers Aw-thor-ih-tee'),
    # --- Dominion & Alpha/Beta quadrant (longer phrases first) ---
    (re.compile(r"\bJem'?Hadars\b", re.IGNORECASE), 'Jem-hah-darz'),
    (re.compile(r"\bJem'?Hadar\b", re.IGNORECASE), 'Jem-hah-dar'),
    (re.compile(r'\bNausicaans\b', re.IGNORECASE), 'Naw-sik-ee-unz'),
    (re.compile(r'\bNausicaan\b', re.IGNORECASE), 'Naw-sik-ee-un'),
    (re.compile(r'\bTalaxians\b', re.IGNORECASE), 'Tah-lak-see-unz'),
    (re.compile(r'\bTalaxian\b', re.IGNORECASE), 'Tah-lak-see-un'),
    (re.compile(r'\bDenobulans\b', re.IGNORECASE), 'Den-obb-yoo-lunz'),
    (re.compile(r'\bDenobulan\b', re.IGNORECASE), 'Den-obb-yoo-lun'),
    (re.compile(r'\bTellarites\b', re.IGNORECASE), 'Tell-er-ights'),
    (re.compile(r'\bTellarite\b', re.IGNORECASE), 'Tell-er-ight'),
    (re.compile(r'\bCardassians\b', re.IGNORECASE), 'Car-dass-ee-unz'),
    (re.compile(r'\bCardassian\b', re.IGNORECASE), 'Car-dass-ee-un'),
    (re.compile(r'\bBajorians\b', re.IGNORECASE), 'Bay-jor-uns'),
    (re.compile(r'\bBajorian\b', re.IGNORECASE), 'Bay-jor-un'),
    (re.compile(r'\bBajorans\b', re.IGNORECASE), 'Bay-jor-unz'),
    (re.compile(r'\bBajoran\b', re.IGNORECASE), 'Bay-jor-un'),
    (re.compile(r'\bRomulans\b', re.IGNORECASE), 'Rom-yoo-lunz'),
    (re.compile(r'\bRomulan\b', re.IGNORECASE), 'Rom-yoo-lun'),
    (re.compile(r'\bAndorians\b', re.IGNORECASE), 'An-dore-ee-unz'),
    (re.compile(r'\bAndorian\b', re.IGNORECASE), 'An-dore-ee-un'),
    (re.compile(r'\bBolians\b', re.IGNORECASE), 'Bow-lee-unz'),
    (re.compile(r'\bBolian\b', re.IGNORECASE), 'Bow-lee-un'),
    (re.compile(r'\bCaitians\b', re.IGNORECASE), 'Kay-shunz'),
    (re.compile(r'\bCaitian\b', re.IGNORECASE), 'Kay-shun'),
    (re.compile(r'\bOrions\b', re.IGNORECASE), 'Oh-ree-unz'),
    (re.compile(r'\bOrion\b', re.IGNORECASE), 'Oh-ree-un'),
    (re.compile(r'\bSulibans\b', re.IGNORECASE), 'Soo-lee-bunz'),
    (re.compile(r'\bSuliban\b', re.IGNORECASE), 'Soo-lee-bun'),
    (re.compile(r'\bHirogen\b', re.IGNORECASE), 'High-row-jen'),
    (re.compile(r'\bRemans\b', re.IGNORECASE), 'Ree-munz'),
    (re.compile(r'\bReman\b', re.IGNORECASE), 'Ree-mun'),
    (re.compile(r'\bChangelings\b', re.IGNORECASE), 'Change-lingz'),
    (re.compile(r'\bChangeling\b', re.IGNORECASE), 'Change-ling'),
    (re.compile(r'\bFounders\b', re.IGNORECASE), 'Fown-ders'),
    (re.compile(r'\bFounder\b', re.IGNORECASE), 'Fown-der'),
    (re.compile(r'\bProphets\b', re.IGNORECASE), 'Prof-its'),
    (re.compile(r'\bProphet\b', re.IGNORECASE), 'Prof-it'),
    (re.compile(r'\bPah-?wraiths\b', re.IGNORECASE), 'Pah-rayths'),
    (re.compile(r'\bPah-?wraith\b', re.IGNORECASE), 'Pah-rayth'),
    (re.compile(r'\bEl-?Aurians\b', re.IGNORECASE), 'El-aw-ree-unz'),
    (re.compile(r'\bEl-?Aurian\b', re.IGNORECASE), 'El-aw-ree-un'),
    (re.compile(r'\bSymbionts\b', re.IGNORECASE), 'Sim-bee-onts'),
    (re.compile(r'\bSymbiont\b', re.IGNORECASE), 'Sim-bee-ont'),
    (re.compile(r'\bTrills\b', re.IGNORECASE), 'Trillz'),
    (re.compile(r'\bTrill\b'), 'Trill'),
    (re.compile(r'\bVulcans\b', re.IGNORECASE), 'Vul-kunz'),
    (re.compile(r'\bVulcan\b', re.IGNORECASE), 'Vul-kun'),
    (re.compile(r'\bKlingons\b', re.IGNORECASE), 'Kling-onz'),
    (re.compile(r'\bKlingon\b', re.IGNORECASE), 'Kling-on'),
    # Soft G as in screen Trek ("ghee"), not "Fereng-ee".
    (re.compile(r'\bFerenginar\b', re.IGNORECASE), 'Feh-ren-jee-nar'),
    (re.compile(r'\bFerengis\b', re.IGNORECASE), 'Feh-ren-jeez'),
    (re.compile(r'\bFerengi\b', re.IGNORECASE), 'Feh-ren-jee'),
    (re.compile(r'\bBetazoids\b', re.IGNORECASE), 'Bay-tah-zoydz'),
    (re.compile(r'\bBetazoid\b', re.IGNORECASE), 'Bay-tah-zoyd'),
    (re.compile(r'\bBreen\b', re.IGNORECASE), 'Breen'),
    (re.compile(r'\bGorn\b', re.IGNORECASE), 'Gorn'),
    (re.compile(r'\bHorta\b', re.IGNORECASE), 'Hor-tah'),
    (re.compile(r'\bBorg\b', re.IGNORECASE), 'Borg'),
    (re.compile(r'\bTribbles\b', re.IGNORECASE), 'Trib-ulz'),
    (re.compile(r'\bTribble\b', re.IGNORECASE), 'Trib-ul'),
    (re.compile(r'\bQomar\b', re.IGNORECASE), 'Koh-mar'),
    # --- More Alpha/Beta/Delta/Gamma species & polities (plurals before stems) ---
    (re.compile(r'\bTholian Assembly\b', re.IGNORECASE), 'Tho-lee-un Uh-sem-blee'),
    (re.compile(r'\bTholians\b', re.IGNORECASE), 'Tho-lee-unz'),
    (re.compile(r'\bTholian\b', re.IGNORECASE), 'Tho-lee-un'),
    (re.compile(r'\bBenzites\b', re.IGNORECASE), 'Benz-ights'),
    (re.compile(r'\bBenzite\b', re.IGNORECASE), 'Benz-ight'),
    (re.compile(r'\bPakleds\b', re.IGNORECASE), 'Pak-ledz'),
    (re.compile(r'\bPakled\b', re.IGNORECASE), 'Pak-led'),
    (re.compile(r'\bTamarians\b', re.IGNORECASE), 'Tah-mair-ee-unz'),
    (re.compile(r'\bTamarian\b', re.IGNORECASE), 'Tah-mair-ee-un'),
    (re.compile(r'\bChildren of Tama\b', re.IGNORECASE), 'Children of Tah-mah'),
    (re.compile(r'\bTama\b', re.IGNORECASE), 'Tah-mah'),
    (re.compile(r'\bYridians\b', re.IGNORECASE), 'Yrid-ee-unz'),
    (re.compile(r'\bYridian\b', re.IGNORECASE), 'Yrid-ee-un'),
    (re.compile(r'\bLurians\b', re.IGNORECASE), 'Loor-ee-unz'),
    (re.compile(r'\bLurian\b', re.IGNORECASE), 'Loor-ee-un'),
    (re.compile(r'\bOrganians\b', re.IGNORECASE), 'Or-gay-nee-unz'),
    (re.compile(r'\bOrganian\b', re.IGNORECASE), 'Or-gay-nee-un'),
    (re.compile(r'\bMedusans\b', re.IGNORECASE), 'Meh-doo-zunz'),
    (re.compile(r'\bMedusan\b', re.IGNORECASE), 'Meh-doo-zun'),
    (re.compile(r'\bDeltans\b', re.IGNORECASE), 'Dell-tunz'),
    (re.compile(r'\bDeltan\b', re.IGNORECASE), 'Dell-tun'),
    (re.compile(r'\bMintakans\b', re.IGNORECASE), 'Min-tah-kunz'),
    (re.compile(r'\bMintakan\b', re.IGNORECASE), 'Min-tah-kun'),
    (re.compile(r'\bAcamarians\b', re.IGNORECASE), 'Ack-uh-mair-ee-unz'),
    (re.compile(r'\bAcamarian\b', re.IGNORECASE), 'Ack-uh-mair-ee-un'),
    (re.compile(r'\bZalkonians\b', re.IGNORECASE), 'Zal-koh-nee-unz'),
    (re.compile(r'\bZalkonian\b', re.IGNORECASE), 'Zal-koh-nee-un'),
    (re.compile(r'\bAntedeans\b', re.IGNORECASE), 'An-teh-dee-unz'),
    (re.compile(r'\bAntedean\b', re.IGNORECASE), 'An-teh-dee-un'),
    (re.compile(r'\bSkrreeans\b', re.IGNORECASE), 'Skree-uns'),
    (re.compile(r'\bSkrreean\b', re.IGNORECASE), 'Skree-un'),
    (re.compile(r'\bEfrosians\b', re.IGNORECASE), 'Eff-roh-zhunz'),
    (re.compile(r'\bEfrosian\b', re.IGNORECASE), 'Eff-roh-zhun'),
    (re.compile(r'\bIyaarans\b', re.IGNORECASE), 'Eye-yah-runz'),
    (re.compile(r'\bIyaaran\b', re.IGNORECASE), 'Eye-yah-run'),
    (re.compile(r'\bGrazerites\b', re.IGNORECASE), 'Gray-zur-ights'),
    (re.compile(r'\bGrazerite\b', re.IGNORECASE), 'Gray-zur-ight'),
    (re.compile(r'\bArdanans\b', re.IGNORECASE), 'Ar-day-nunz'),
    (re.compile(r'\bArdanan\b', re.IGNORECASE), 'Ar-day-nun'),
    (re.compile(r'\bAngosians\b', re.IGNORECASE), 'An-goh-see-unz'),
    (re.compile(r'\bAngosian\b', re.IGNORECASE), 'An-goh-see-un'),
    (re.compile(r'\bRutians\b', re.IGNORECASE), 'Roo-shee-unz'),
    (re.compile(r'\bRutian\b', re.IGNORECASE), 'Roo-shee-un'),
    (re.compile(r'\bParadas\b', re.IGNORECASE), 'Puh-rah-duhz'),
    (re.compile(r'\bParada\b', re.IGNORECASE), 'Puh-rah-duh'),
    (re.compile(r'\bKelleruns\b', re.IGNORECASE), 'Kell-er-unz'),
    (re.compile(r'\bKellerun\b', re.IGNORECASE), 'Kell-er-un'),
    (re.compile(r"\bT'Lanis\b", re.IGNORECASE), 'Tee-lah-neez'),
    (re.compile(r"\bT'Lani\b", re.IGNORECASE), 'Tee-lah-nee'),
    (re.compile(r'\bLysians\b', re.IGNORECASE), 'Liss-ee-unz'),
    (re.compile(r'\bLysian\b', re.IGNORECASE), 'Liss-ee-un'),
    (re.compile(r'\bSheliak\b', re.IGNORECASE), 'Shell-ee-ak'),
    (re.compile(r'\bEdo\b', re.IGNORECASE), 'Ee-doh'),
    (re.compile(r'\bMalons\b', re.IGNORECASE), 'Mal-onz'),
    (re.compile(r'\bMalon\b', re.IGNORECASE), 'Mal-on'),
    (re.compile(r'\bNygeans\b', re.IGNORECASE), 'Nye-jee-unz'),
    (re.compile(r'\bNygean\b', re.IGNORECASE), 'Nye-jee-un'),
    (re.compile(r'\bDevore\b', re.IGNORECASE), 'Deh-vor'),
    (re.compile(r'\bHazari\b', re.IGNORECASE), 'Hah-zah-ree'),
    (re.compile(r'\bKrenim\b', re.IGNORECASE), 'Kreh-nim'),
    (re.compile(r'\bVaadwaur\b', re.IGNORECASE), 'Vahd-wor'),
    (re.compile(r'\bVidiian\b', re.IGNORECASE), 'Vih-dee-un'),
    (re.compile(r'\bVidiians\b', re.IGNORECASE), 'Vih-dee-unz'),
    (re.compile(r'\bVoth\b', re.IGNORECASE), 'Vawth'),
    (re.compile(r'\bKazon\b', re.IGNORECASE), 'Kay-zon'),
    (re.compile(r'\bKazons\b', re.IGNORECASE), 'Kay-zonz'),
    (re.compile(r'\bXindi\b', re.IGNORECASE), 'Zin-dee'),
    (re.compile(r'\bXindi-Arboreals\b', re.IGNORECASE), 'Zin-dee Ar-bor-ee-ulz'),
    (re.compile(r'\bXindi-Aquatics\b', re.IGNORECASE), 'Zin-dee Uh-kwat-iks'),
    (re.compile(r'\bXindi-Insectoids\b', re.IGNORECASE), 'Zin-dee In-sek-toydz'),
    (re.compile(r'\bXindi-Primates\b', re.IGNORECASE), 'Zin-dee Pry-mates'),
    (re.compile(r'\bXindi-Reptilians\b', re.IGNORECASE), 'Zin-dee Rep-till-ee-unz'),
    (re.compile(r'\bXindi-Reptilian\b', re.IGNORECASE), 'Zin-dee Rep-till-ee-un'),
    (re.compile(r'\bXindi-Arboreal\b', re.IGNORECASE), 'Zin-dee Ar-bor-ee-ul'),
    (re.compile(r'\bXindi-Aquatic\b', re.IGNORECASE), 'Zin-dee Uh-kwat-ik'),
    (re.compile(r'\bXindi-Insectoid\b', re.IGNORECASE), 'Zin-dee In-sek-toyd'),
    (re.compile(r'\bXindi-Primate\b', re.IGNORECASE), 'Zin-dee Pry-mate'),
    (re.compile(r'\bSphere-Builders\b', re.IGNORECASE), 'Sphere Builders'),
    (re.compile(r'\bUndine\b', re.IGNORECASE), 'Un-deen'),
    (re.compile(r'\bSpecies 8472\b', re.IGNORECASE), 'Species eight four seven two'),
    (re.compile(r'\bDopterians\b', re.IGNORECASE), 'Dop-teer-ee-unz'),
    (re.compile(r'\bDopterian\b', re.IGNORECASE), 'Dop-teer-ee-un'),
    (re.compile(r'\bZakdorn\b', re.IGNORECASE), 'Zak-dorn'),
    (re.compile(r'\bZakdorns\b', re.IGNORECASE), 'Zak-dornz'),
    (re.compile(r'\bKreetassans\b', re.IGNORECASE), 'Kree-tass-unz'),
    (re.compile(r'\bKreetassan\b', re.IGNORECASE), 'Kree-tass-un'),
    (re.compile(r'\bCoridanites\b', re.IGNORECASE), 'Kor-ih-dan-ights'),
    (re.compile(r'\bCoridanite\b', re.IGNORECASE), 'Kor-ih-dan-ight'),
    (re.compile(r'\bCoridan\b', re.IGNORECASE), 'Kor-ih-dan'),
]


_STARDATE_RE = re.compile(
    r'\b(?P<label>[Ss]tardate)\s*:?\s*(?P<num>[\d][\d\s,]*\.?[\d\s,]*)'
)


def _expand_stardate_number(raw: str) -> str:
    """Turn a stardate numeral into spoken digits (e.g. 3190.1 → word digits)."""
    t = raw.replace(',', '').replace(' ', '')
    if not any(c.isdigit() for c in t):
        return raw
    if '.' in t:
        whole, frac = t.split('.', 1)
        whole_d = ''.join(c for c in whole if c.isdigit())
        frac_d = ''.join(c for c in frac if c.isdigit())
        if not whole_d:
            return raw
        spoken = _spell_digits(whole_d)
        if frac_d:
            spoken = f'{spoken} point {_spell_digits(frac_d)}'
        return spoken
    whole_d = ''.join(c for c in t if c.isdigit())
    return _spell_digits(whole_d) if whole_d else raw


def expand_stardates_for_speech(text: str) -> str:
    """Replace ``Stardate 47215.2`` with spoken digit form (no cardinal thousands)."""

    def _sub(m: re.Match[str]) -> str:
        label = m.group('label')
        return f'{label} {_expand_stardate_number(m.group("num"))}'

    return _STARDATE_RE.sub(_sub, text)


def apply_trek_lexicon(text: str) -> str:
    """Apply species and name respellings."""
    out = text
    for pat, repl in _LEXICON:
        out = pat.sub(repl, out)
    return out


def normalize_trek_tts_text(text: str) -> str:
    """Full pipeline for dialogue and narration sent to TTS."""
    if not text:
        return text
    t = expand_stardates_for_speech(text)
    t = apply_trek_lexicon(t)
    return t
