import { describe, expect, it } from 'vitest'
import { getConfirmedOfficialLogo } from '../scholarshipLogos'

describe('getConfirmedOfficialLogo', () => {
  it('uses an audited official logo for the scholarship provider', () => {
    const logo = getConfirmedOfficialLogo({
      title: 'Erasmus Mundus',
      official_source_url: 'https://erasmus-plus.ec.europa.eu/opportunities',
    })

    expect(logo).toEqual({
      url: expect.stringMatching(/^https:\/\//),
      altText: 'Erasmus+ European Commission',
    })
  })

  it('does not present an official programme photo or banner as a logo', () => {
    expect(getConfirmedOfficialLogo({
      title: 'Scholarship',
      official_source_url: 'https://unmapped.example.org/programme',
      image_url: 'https://unmapped.example.org/banner.jpg',
      image_kind: 'program_image',
      image_source_type: 'official_scholarship',
      image_verified_at: '2026-10-01',
    })).toBeNull()
  })

  it('accepts explicit official-logo metadata from a scholarship record', () => {
    expect(getConfirmedOfficialLogo({
      title: 'Example Scholarship',
      image_url: 'https://example.org/logo.svg',
      image_kind: 'official_logo',
    })).toEqual({
      url: 'https://example.org/logo.svg',
      altText: 'Example Scholarship official provider logo',
    })
  })
})
