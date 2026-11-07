with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the allScholarships useMemo block
old_block = '''  // Combine flagship scholarships with directory for maximum data richness
  const allScholarships = useMemo(() => {
    const flagTitles = new Set(FLAGSHIP_PROGRAMMES.map((f) => f.title.toLowerCase()))
    const extra = (directoryScholarships || [])
      .filter((s) => !flagTitles.has((s.title || '').toLowerCase()))
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
        provider: s.provider || `\${s.country} Education Board`,
        verified: s.verification_status === 'active',
        image_url: s.image_url,
        image_source_url: s.image_source_url,
        image_source_type: s.image_source_type,
        image_kind: s.image_kind,
        image_verified_at: s.image_verified_at,
        image_alt_text: s.image_alt_text,
      }))
    return [...FLAGSHIP_PROGRAMMES, ...extra]
  }, [directoryScholarships])'''

new_block = '''  // Use directory scholarships directly (no hardcoded flagship programmes)
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
        provider: s.provider || `\${s.country} Education Board`,
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

if old_block in content:
    content = content.replace(old_block, new_block)
    print("Replaced allScholarships block")
else:
    print("Could not find exact block")
    # Try to find what's there
    idx = content.find('Combine flagship scholarships')
    if idx != -1:
        print("Found at:", idx)
        print(content[idx:idx+500])

with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")