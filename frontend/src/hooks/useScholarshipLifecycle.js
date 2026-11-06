import { useMemo } from 'react';
import { classifyLifecycle } from '../utils/lifecycle';

export function useScholarshipLifecycle(scholarship) {
  return useMemo(() => classifyLifecycle(scholarship), [scholarship]);
}

export function useScholarshipLifecycles(scholarships) {
  return useMemo(() => {
    const map = new Map();
    scholarships.forEach((scholarship) => {
      map.set(String(scholarship.id), classifyLifecycle(scholarship));
    });
    return map;
  }, [scholarships]);
}

export function useLifecycleFilter(scholarships, selectedLifecycle) {
  return useMemo(() => {
    if (!selectedLifecycle || selectedLifecycle === 'all') {
      return scholarships;
    }
    return scholarships.filter((scholarship) => {
      const lifecycle = classifyLifecycle(scholarship);
      return lifecycle.status === selectedLifecycle;
    });
  }, [scholarships, selectedLifecycle]);
}

export function useLifecycleCounts(scholarships) {
  return useMemo(() => {
    const counts = {
      opening: 0,
      upcoming: 0,
      closing_soon: 0,
      closed: 0,
      open: 0,
      unknown: 0,
    };

    scholarships.forEach((scholarship) => {
      const lifecycle = classifyLifecycle(scholarship);
      if (Object.hasOwn(counts, lifecycle.status)) {
        counts[lifecycle.status]++;
      }
    });

    return counts;
  }, [scholarships]);
}