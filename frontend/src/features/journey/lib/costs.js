/**
 * Cost totals, funding gap and currency conversion.
 *
 * The formula this module implements, stated once so it can be checked:
 *
 *   totalEstimatedCost = Σ usable amounts of cost items whose category is not
 *                        `funding`
 *   totalFunding       = Σ usable amounts of cost items whose category is
 *                        `funding`
 *   gap                = totalEstimatedCost − totalFunding
 *
 * A negative gap is a **surplus**, and it is reported as `state: 'surplus'`
 * rather than being clamped to zero. Clamping would hide the case where the
 * recorded coverage exceeds the recorded cost, which is usually a data-entry
 * error the student wants to see.
 *
 * `state` is one of:
 *   - `no-costs`    : nothing usable has been recorded as a cost
 *   - `no-funding`  : costs are known but no coverage has been recorded
 *   - `gap`         : coverage is short of the costs
 *   - `surplus`     : coverage meets or exceeds the costs
 *
 * `gap` is a Number or null, deliberately. `totalCost` and `totalFunding` are
 * canonical decimal *strings* because they are what the student typed, rounded
 * through integer cents; `gap` is the one figure that is always arithmetic, so
 * it is a Number. `containsEstimates` is true when at least one contributing
 * figure is an estimate or is user-entered rather than official. It is computed
 * from the provenance labels and never from the magnitude of the numbers, and
 * every surface that shows a total is required to show it alongside this flag.
 */

import {
  COST_CATEGORIES,
  FUNDING_CATEGORY,
  normalizeAmount,
  amountToNumber,
  convertToBdt,
  sumAmounts,
} from './money.js'

/** A cost item that is a cost rather than funding. */
function isCostItem(item) {
  return item.category !== FUNDING_CATEGORY
}

/** A usable amount, or null when the text is not a number. */
function usableAmount(item) {
  return amountToNumber(normalizeAmount(item.amount))
}

/**
 * Group funding by provenance.
 *
 * Split because "the scholarship is stated by the provider to cover this" and
 * "the student believes it covers this" are different claims, and a total that
 * merges them overstates how well-supported the number is.
 */
export function fundingBySourceType(items) {
  const out = { official: [], 'user-entered': [], estimate: [] }
  for (const item of items) {
    if (item.category !== FUNDING_CATEGORY) continue
    if (usableAmount(item) === null) continue
    const bucket = out[item.sourceType] || out['user-entered']
    bucket.push(item)
  }
  return out
}

/**
 * The full picture for one cost plan.
 *
 * `unusableItemIds` lists lines whose amount could not be read, so the UI can
 * point at them instead of silently dropping them from the total.
 */
export function computeCostSummary(doc) {
  const items = Array.isArray(doc?.costs?.items) ? doc.costs.items : []

  const costItems = items.filter(isCostItem)
  const fundingItems = items.filter((item) => item.category === FUNDING_CATEGORY)

  const costAmounts = costItems.map((item) => item.amount)
  const fundingAmounts = fundingItems.map((item) => item.amount)

  const costSum = sumAmounts(costAmounts)
  const fundingSum = sumAmounts(fundingAmounts)

  const totalCost = Number(costSum.total)
  const totalFunding = Number(fundingSum.total)

  const byCategory = {}
  for (const category of COST_CATEGORIES) {
    const matching = costItems.filter((item) => item.category === category)
    const sum = sumAmounts(matching.map((item) => item.amount))
    byCategory[category] = {
      total: sum.total,
      usable: sum.usable,
      count: matching.length,
    }
  }

  const usableCosts = costItems.filter((item) => usableAmount(item) !== null).length
  const usableFunding = fundingItems.filter((item) => usableAmount(item) !== null).length

  const containsEstimate = [...costItems, ...fundingItems].some(
    (item) => item.sourceType === 'estimate' || item.sourceType === 'user-entered',
  )
  const containsOfficialOnly =
    [...costItems, ...fundingItems].length > 0 &&
    [...costItems, ...fundingItems].every((item) => item.sourceType === 'official')

  const unusableItemIds = items
    .filter((item) => normalizeAmount(item.amount).ok === false && item.amount.trim() !== '')
    .map((item) => item.id)

  let state = 'no-costs'
  let gap = null
  if (usableCosts > 0) {
    if (usableFunding === 0) {
      state = 'no-funding'
      gap = totalCost
    } else if (totalFunding < totalCost) {
      state = 'gap'
      gap = totalCost - totalFunding
    } else {
      state = 'surplus'
      gap = totalCost - totalFunding
    }
  }

  return {
    totalCost: costSum.total,
    totalFunding: fundingSum.total,
    totalCostUsable: costSum.usable,
    totalFundingUsable: fundingSum.usable,
    gap,
    state,
    containsEstimate,
    containsOfficialOnly,
    byCategory,
    usableCosts,
    usableFunding,
    unusableItemIds,
  }
}

/**
 * Convert a cost plan into BDT using the rate the student recorded.
 *
 * Returns per-item conversions plus a converted total. Anything the rate cannot
 * convert is listed in `unconverted` rather than dropped, so the student can see
 * which lines the plan could not translate and why.
 */
export function computeBdtView(doc) {
  const items = Array.isArray(doc?.costs?.items) ? doc.costs.items : []
  const rate = doc?.costs?.rate ?? {}
  const rateUsable = amountToNumber(normalizeAmount(rate.bdtPerUnit))

  const lines = items.map((item) => {
    const amount = normalizeAmount(item.amount)
    if (!amount.ok) {
      return { id: item.id, converted: null, reason: 'invalid-amount' }
    }
    if (item.currency === 'BDT') {
      return { id: item.id, converted: amount.value, reason: 'already-bdt', rateUsed: null }
    }
    if (rateUsable === null || rateUsable <= 0) {
      return { id: item.id, converted: null, reason: 'no-rate' }
    }
    const converted = convertToBdt(amount.value, rate.bdtPerUnit)
    if (converted === null) {
      return { id: item.id, converted: null, reason: 'no-rate' }
    }
    return {
      id: item.id,
      converted: converted.amount,
      reason: 'converted',
      rateUsed: converted.rateUsed,
    }
  })

  const unconverted = lines.filter((line) => line.converted === null)

  const costLines = items
    .filter(isCostItem)
    .map((item) => lines.find((line) => line.id === item.id))
    .filter((line) => line && line.converted !== null)
  const fundingLines = items
    .filter((item) => item.category === FUNDING_CATEGORY)
    .map((item) => lines.find((line) => line.id === item.id))
    .filter((line) => line && line.converted !== null)

  const costSum = sumAmounts(costLines.map((line) => line.converted))
  const fundingSum = sumAmounts(fundingLines.map((line) => line.converted))

  return {
    rateUsed: rateUsable === null ? null : String(rateUsable),
    effectiveDate: rate.effectiveDate || '',
    lines,
    unconverted,
    totalCostBdt: costSum.total,
    totalFundingBdt: fundingSum.total,
    gapBdt:
      costSum.total === '0' && fundingSum.total === '0'
        ? null
        : (Number(costSum.total) - Number(fundingSum.total)).toFixed(2).replace(/\.?0+$/, ''),
  }
}
