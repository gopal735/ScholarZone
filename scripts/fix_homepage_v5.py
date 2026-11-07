with open('frontend/src/pages/HomePage.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace the allScholarships block
# Look for the specific pattern
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Look for the start of the block
    if 'Combine flagship scholarships with directory for maximum data richness' in line:
        # Skip until the closing brace of the useMemo
        new_lines.append('  // Use directory scholarships directly (no hardcoded flagship programmes)\n')
        new_lines.append('  const allScholarships = useMemo(() => {\n')
        new_lines.append('    const extra = (directoryScholarships || [])\n')
        new_lines.append('      .slice(0, 48) // Rich batch from the 725+ catalogue\n')
        new_lines.append('      .map((s) => ({\n')
        new_lines.append("        id: s.id,\n")
        new_lines.append("        title: s.title,\n")
        new_lines.append("        country: s.country,\n")
        new_lines.append("        degree: s.degree || \"Master's, PhD\",\n")
        new_lines.append("        funding: s.funding || (s.fully_funded ? 'Fully Funded' : 'Partial'),\n")
        new_lines.append("        levels: s.degree ? [s.degree] : [\"Master's\"],\n")
        new_lines.append("        isFull: s.funding === 'Fully Funded' || !!s.fully_funded,\n")
        new_lines.append("        coverage: s.description || s.benefits || `Study opportunity in ${s.country}. Check official website for detailed eligibility.`,")
        new_lines.append("        officialUrl: s.official_source_url || s.application_link,\n")
        new_lines.append("        provider: s.provider || `${s.country} Education Board`,\n")
        new_lines.append("        verified: s.verification_status === 'active',")
        new_lines.append("        image_url: s.image_url,\n")
        new_lines.append("        image_source_url: s.image_source_url,\n")
        new_lines.append("        image_source_type: s.image_source_type,\n")
        new_lines.append("        image_kind: s.image_kind,\n")
        new_lines.append("        image_verified_at: s.image_verified_at,\n")
        new_lines.append("        image_alt_text: s.image_alt_text,\n")
        new_lines.append("      }))\n")
        new_lines.append("    return extra\n")
        new_lines.append("  }, [directoryScholarships])\n")
        
        # Skip the old block - find the closing brace of the useMemo
        i += 1
        brace_count = 0
        while i < len(lines):
            if 'useMemo(() => {' in lines[i]:
                brace_count += 1
            if '{' in lines[i]:
                brace_count += lines[i].count('{')
            if '}' in lines[i]:
                brace_count -= lines[i].count('}')
                if brace_count <= 0:
                    i += 1
                    break
            i += 1
        continue
    new_lines.append(line)
    i += 1

with open('frontend/src/pages/HomePage.jsx', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Done")