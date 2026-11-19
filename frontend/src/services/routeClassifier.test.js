import { describe, it, expect } from 'vitest'
import { classifyRoute } from '../services/routeClassifier'

describe('routeClassifier', () => {
  describe('discovery routes', () => {
    it('classifies "Find PhD scholarships with stipend in Europe" as discovery', () => {
      expect(classifyRoute('Find PhD scholarships with stipend in Europe')).toBe('discovery')
    })

    it('classifies "Find fully funded Master\'s scholarships in Germany" as discovery', () => {
      expect(classifyRoute("Find fully funded Master's scholarships in Germany")).toBe('discovery')
    })

    it('classifies "Which scholarships have deadlines in the next 30 days?" as discovery', () => {
      expect(classifyRoute('Which scholarships have deadlines in the next 30 days?')).toBe('discovery')
    })

    it('classifies "Search scholarships in Japan" as discovery', () => {
      expect(classifyRoute('Search scholarships in Japan')).toBe('discovery')
    })

    it('classifies "Find PhD scholarships with stipend in Europe" (exact reported query) as discovery', () => {
      expect(classifyRoute('Find PhD scholarships with stipend in Europe')).toBe('discovery')
    })
  })

  describe('private mentor routes', () => {
    it('classifies "Can I apply for fully funded scholarships with my GPA of 2.5?" as mentor', () => {
      expect(classifyRoute('Can I apply for fully funded scholarships with my GPA of 2.5?')).toBe('mentor')
    })

    it('classifies "Am I eligible based on my grades?" as mentor', () => {
      expect(classifyRoute('Am I eligible based on my grades?')).toBe('mentor')
    })

    it('classifies "Do I qualify with my academic profile?" as mentor', () => {
      expect(classifyRoute('Do I qualify with my academic profile?')).toBe('mentor')
    })

    it('classifies "Can I apply with my current GPA?" as mentor', () => {
      expect(classifyRoute('Can I apply with my current GPA?')).toBe('mentor')
    })

    it('classifies "Which scholarships match my profile?" as mentor', () => {
      expect(classifyRoute('Which scholarships match my profile?')).toBe('mentor')
    })

    it('classifies "Am I eligible for this scholarship?" as mentor', () => {
      expect(classifyRoute('Am I eligible for this scholarship?')).toBe('mentor')
    })

    it('classifies "What are my saved scholarships?" as mentor', () => {
      expect(classifyRoute('What are my saved scholarships?')).toBe('mentor')
    })

    it('classifies "What should I do next?" as mentor', () => {
      expect(classifyRoute('What should I do next?')).toBe('mentor')
    })
  })

  describe('first-person eligibility takes precedence', () => {
    it('classifies "Can I apply for fully funded scholarships with my GPA of 2.5?" as mentor even though it contains discovery words', () => {
      expect(classifyRoute('Can I apply for fully funded scholarships with my GPA of 2.5?')).toBe('mentor')
    })

    it('classifies "Which scholarships match my profile?" as mentor even though it contains discovery words', () => {
      expect(classifyRoute('Which scholarships match my profile?')).toBe('mentor')
    })
  })

  describe('personal disclosure (health, financial, legal)', () => {
    it('classifies "Find scholarships for me; my HIV diagnosis is positive" as mentor', () => {
      expect(classifyRoute('Find scholarships for me; my HIV diagnosis is positive')).toBe('mentor')
    })

    it('classifies "Find scholarships for me; I was diagnosed with cancer" as mentor', () => {
      expect(classifyRoute('Find scholarships for me; I was diagnosed with cancer')).toBe('mentor')
    })

    it('classifies "Find scholarships; my disability affects my studies" as mentor', () => {
      expect(classifyRoute('Find scholarships; my disability affects my studies')).toBe('mentor')
    })

    it('classifies "Find scholarships; my income is below poverty line" as mentor', () => {
      expect(classifyRoute('Find scholarships; my income is below poverty line')).toBe('mentor')
    })

    it('classifies "Find scholarships; my visa status is pending" as mentor', () => {
      expect(classifyRoute('Find scholarships; my visa status is pending')).toBe('mentor')
    })

    it('classifies "Find scholarships; I am pregnant" as mentor', () => {
      expect(classifyRoute('Find scholarships; I am pregnant')).toBe('mentor')
    })
  })

  describe('edge cases', () => {
    it('classifies empty string as mentor (safe default)', () => {
      expect(classifyRoute('')).toBe('mentor')
    })

    it('classifies null as mentor (safe default)', () => {
      expect(classifyRoute(null)).toBe('mentor')
    })

    it('classifies undefined as mentor (safe default)', () => {
      expect(classifyRoute(undefined)).toBe('mentor')
    })

    it('classifies ambiguous input as mentor (safe default)', () => {
      expect(classifyRoute('scholarship')).toBe('mentor')
    })
  })
})
