import re

with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Use regex to replace the allScholarships block
pattern = r'// Combine flagship scholarships with directory for maximum data richness\s*const allScholarships = useMemo\(\(\) => \{\s*const flagTitles = new Set\(FLAGSHIP_PROGRAMMES\.map\(\(f\) => f\.title\.toLowerCase\(\)\)\)\s*const extra = \(directoryScholarships \|\| \[\]\)\s*\.filter\(\(s\) => !flagTitles\.has\(\(s\.title \|\| \x27\x27\)\.toLowerCase\(\)\)\)\s*\.slice\(0, 48\)\s*\.map\(\(s\) => \(\{\s*id: s\.id,\s*title: s\.title,\s*country: s\.country,\s*degree: s\.degree \|\| "Master\x27s, PhD",\s*funding: s\.funding \|\| \(s\.fully_funded \? \x27Fully Funded\x27 : \x27Partial\x27\),\s*levels: s\.degree \? \[s\.degree\] : \["Master\x27s"\],\s*isFull: s\.funding === \x27Fully Funded\x27 \|\| !!s\.fully_funded,\s*coverage: s\.description \|\| s\.benefits \|\| `Study opportunity in \$\{s\.country\}\. Check official website for detailed eligibility\.`,\s*officialUrl: s\.official_source_url \|\| s\.application_link,\s*provider: s\.provider \|\| `\$\{s\.country\} Education Board`,\s*verified: s\.verification_status === \x27active\x27,\s*image_url: s\.image_url,\s*image_source_url: s\.image_source_url,\s*image_source_type: s\.image_source_type,\s*image_kind: s\.image_kind,\s*image_verified_at: s\.image_verified_at,\s*image_alt_text: s\.image_alt_text,\s*\}\)\s*return \[\.\.\.FLAGSHIP_PROGRAMMES, \.\.\.extra\]\s*\}, \[directoryScholarships\])'

replacement = '''  // Use directory scholarships directly (no hardcoded flagship programmes)
  const allScholarships = useMemo(() => {
    const extra = (directoryScholarships || [])
      .slice(0, 48) // Rich batch from the 725+ catalogue
      .map((s) => ({
        id: s.id,
        title: s.title,
        country: s.country,
        degree: s.degree || "Master's, PhD",
        funding: s.funding || (s.fully_funded ? 'Fully Funded' : 'Partial'),
        levels: s.degree ? [s.degree] : ["Master's"],
        isFull: s.funding === 'Fully Funded' || !!s.fully_funded,
        coverage: s.description || s.benefits || `Study opportunity in ${s.country}. Check official website for detailed eligibility.`,
        officialUrl: s.official_source_url || s.application_link,
        provider: s.provider || `${s.country} Education Board`,
        verified: s.verification_status === 'active',
        image_url: s.image_url,
        image_source_url: s.image_source_url,
        image_source_type: s.image_source_type,
        image_kind: s.image_kind,
        image_verified_at: s.image_verified_at,
        image_alt_text: s.image_alt_text,
      }))
    return extra
  }, [directoryScholarships])'''

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")