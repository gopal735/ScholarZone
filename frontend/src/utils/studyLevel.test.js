/**
 * Study-level derivation.
 *
 * The catalogue's degree strings are a 164-value free-text field where most
 * values are held by a single record, so a filter over the literals is a
 * 164-entry menu that mostly matches one scholarship. These tests pin the
 * derivation that makes the filter usable instead, and above all they pin the
 * two cases where a wrong answer is a lie rather than an inconvenience:
 *
 *   - a record that names no level must not be reported as accepting any level
 *   - a record listing three of five levels must not be reported as "any"
 */

import { describe, expect, it } from 'vitest'
import {
  getStudyLevels,
  matchesStudyLevel,
  studyLevelLabel,
  STUDY_LEVELS,
  UNSPECIFIED_LEVEL,
} from './studyLevel.js'

describe('getStudyLevels', () => {
  it('names every level a multi-level record accepts', () => {
    // Real shapes from the snapshot, not invented ones.
    expect(getStudyLevels({ degree: "Bachelor's, Master's, PhD" })).toEqual(
      expect.arrayContaining(['bachelor', 'master', 'doctoral']),
    )
    expect(getStudyLevels({ degree_levels: 'Undergraduate, Graduate (Master\'s, Doctoral) - exchange only' })).toEqual(
      expect.arrayContaining(['bachelor', 'master', 'doctoral']),
    )
  })

  it('distinguishes a postdoc from a doctoral record', () => {
    // "PhD, Postdoc" carries a doctoral stem, so a naive match would report
    // doctoral only and lose the postdoc bucket entirely.
    const levels = getStudyLevels({ degree: 'PhD, Postdoc' })
    expect(levels).toContain('postdoc')
    expect(levels).toContain('doctoral')
  })

  it('reads a level out of a long descriptive string', () => {
    expect(getStudyLevels({
      degree_levels: "Master's degree programme: integrated master's track with a research year",
    })).toContain('master')
  })

  it('recognises abbreviations and word stems', () => {
    expect(getStudyLevels({ degree: 'M.A.Sc' })).toContain('master')
    expect(getStudyLevels({ degree: 'MSc' })).toContain('master')
    expect(getStudyLevels({ degree: 'PhD' })).toContain('doctoral')
    expect(getStudyLevels({ degree: 'DPhil (PhD)' })).toContain('doctoral')
    expect(getStudyLevels({ degree: 'B.Tech' })).toContain('bachelor')
    expect(getStudyLevels({ degree: 'UG (Bachelor\'s/Associate)' })).toEqual(
      expect.arrayContaining(['bachelor']),
    )
  })

  it('reports unspecified when the degree text names no level', () => {
    // "Any level" is the claim these records do NOT make. Reporting
    // unspecified keeps them findable by a dedicated filter rather than
    // hiding them inside a bucket they were never in.
    expect(getStudyLevels({ degree: 'Research grant' })).toEqual([UNSPECIFIED_LEVEL])
    expect(getStudyLevels({ degree: '' })).toEqual([UNSPECIFIED_LEVEL])
    expect(getStudyLevels({ degree: null })).toEqual([UNSPECIFIED_LEVEL])
    expect(getStudyLevels({})).toEqual([UNSPECIFIED_LEVEL])
  })

  it('reports any only for an explicit any-level claim', () => {
    expect(getStudyLevels({ degree_levels: 'Any degree programme at a Charles University faculty' })).toEqual(['any'])
    expect(getStudyLevels({ degree: 'All levels' })).toEqual(['any'])
  })

  it('does not treat a three-of-five listing as any level', () => {
    const levels = getStudyLevels({ degree: "Bachelor's, Master's, PhD" })
    expect(levels).not.toContain('any')
  })

  it('is total for non-object input', () => {
    expect(getStudyLevels(null)).toEqual([UNSPECIFIED_LEVEL])
    expect(getStudyLevels(undefined)).toEqual([UNSPECIFIED_LEVEL])
    expect(getStudyLevels('Master')).toEqual([UNSPECIFIED_LEVEL])
    expect(getStudyLevels(42)).toEqual([UNSPECIFIED_LEVEL])
  })

  it('never returns an empty array', () => {
    // A record in no bucket at all would silently vanish from every level
    // filter, which is the failure this pins.
    const samples = [
      {}, { degree: null }, { degree: '' }, { degree: 'Research grant' },
      { degree_levels: 'varies' }, { degree: 'Master' }, { degree: 'PhD, Postdoc' },
    ]
    for (const sample of samples) {
      expect(getStudyLevels(sample).length).toBeGreaterThan(0)
    }
  })
})

describe('matchesStudyLevel', () => {
  it('matches a record that lists the level among several', () => {
    const record = { degree: "Bachelor's, Master's, PhD" }
    expect(matchesStudyLevel(record, 'bachelor')).toBe(true)
    expect(matchesStudyLevel(record, 'master')).toBe(true)
    expect(matchesStudyLevel(record, 'doctoral')).toBe(true)
  })

  it('does not match a level the record does not list', () => {
    expect(matchesStudyLevel({ degree: 'PhD, Postdoc' }, 'bachelor')).toBe(false)
  })

  it('does not match an unspecified record under a real level', () => {
    // A record naming no level is not evidence it accepts that level.
    expect(matchesStudyLevel({ degree: 'Research grant' }, 'master')).toBe(false)
    expect(matchesStudyLevel({ degree: 'Research grant' }, 'any')).toBe(false)
  })

  it('matches an unspecified record under the unspecified filter', () => {
    expect(matchesStudyLevel({ degree: 'Research grant' }, UNSPECIFIED_LEVEL)).toBe(true)
    expect(matchesStudyLevel({ degree: 'Master' }, UNSPECIFIED_LEVEL)).toBe(false)
  })

  it('treats an empty selection as no filter', () => {
    expect(matchesStudyLevel({ degree: 'Master' }, '')).toBe(true)
    expect(matchesStudyLevel({ degree: 'Master' }, 'all')).toBe(true)
    expect(matchesStudyLevel({ degree: 'Master' }, null)).toBe(true)
  })

  it('does not match any against a record that lists only some levels', () => {
    expect(matchesStudyLevel({ degree: "Bachelor's, Master's" }, 'any')).toBe(false)
  })
})

describe('studyLevelLabel', () => {
  it('labels every exported level', () => {
    for (const level of STUDY_LEVELS) {
      expect(typeof studyLevelLabel(level.value)).toBe('string')
      expect(studyLevelLabel(level.value).length).toBeGreaterThan(0)
    }
  })

  it('labels the unspecified bucket distinctly', () => {
    expect(studyLevelLabel(UNSPECIFIED_LEVEL)).toBe('Level not stated')
  })
})
