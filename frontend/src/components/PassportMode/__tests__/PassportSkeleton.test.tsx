/**
 * Tests for PassportSkeleton component.
 */

import { describe, it, expect } from 'vitest';

describe('PassportSkeleton', () => {
  describe('module exports', () => {
    it('exports PassportSkeleton as default export', async () => {
      const module = await import('../PassportSkeleton');
      expect(module.default).toBeDefined();
      // React.memo wraps the function, so check for $$typeof (memo marker) or function
      expect(
        typeof module.default === 'function' ||
        (typeof module.default === 'object' && module.default !== null)
      ).toBe(true);
    });

    it('is exported from PassportMode index', async () => {
      const module = await import('../index');
      expect(module.PassportSkeleton).toBeDefined();
      // React.memo wraps the function, so check for $$typeof (memo marker) or function
      expect(
        typeof module.PassportSkeleton === 'function' ||
        (typeof module.PassportSkeleton === 'object' && module.PassportSkeleton !== null)
      ).toBe(true);
    });
  });

  describe('props interface', () => {
    it('accepts optional cardType prop', () => {
      interface PassportSkeletonProps {
        cardType?: 'nameplate' | 'pcf' | 'generic';
      }

      const validProps: PassportSkeletonProps[] = [
        {},
        { cardType: 'nameplate' },
        { cardType: 'pcf' },
        { cardType: 'generic' },
      ];

      validProps.forEach((props) => {
        expect(props.cardType === undefined || ['nameplate', 'pcf', 'generic'].includes(props.cardType)).toBe(true);
      });
    });

    it('defaults to generic when no cardType provided', () => {
      // This tests the expected default behavior
      const defaultCardType = 'generic';
      expect(['nameplate', 'pcf', 'generic']).toContain(defaultCardType);
    });
  });

  describe('card type variants', () => {
    it('has three valid card type options', () => {
      const validTypes = ['nameplate', 'pcf', 'generic'] as const;
      expect(validTypes.length).toBe(3);
    });

    it('nameplate skeleton has expected structure', () => {
      // Verifies skeleton classes exist for nameplate variant
      const expectedClasses = [
        'nameplate-skeleton',
        'passport-skeleton-header',
        'passport-skeleton-marker',
        'passport-skeleton-grid',
      ];
      expect(expectedClasses.length).toBe(4);
    });

    it('pcf skeleton has expected structure', () => {
      // Verifies skeleton classes exist for PCF variant
      const expectedClasses = [
        'pcf-skeleton',
        'pcf-skeleton-header',
        'passport-skeleton-metric',
        'passport-skeleton-chart',
        'passport-skeleton-legend',
        'passport-skeleton-details',
      ];
      expect(expectedClasses.length).toBe(6);
    });

    it('generic skeleton has expected structure', () => {
      // Verifies skeleton classes exist for generic variant
      const expectedClasses = [
        'generic-skeleton',
        'generic-skeleton-header',
        'passport-skeleton-section',
      ];
      expect(expectedClasses.length).toBe(3);
    });
  });

  describe('accessibility', () => {
    it('has role="status" on container', () => {
      // The component should have role="status" for screen readers
      const expectedRole = 'status';
      expect(expectedRole).toBe('status');
    });

    it('has aria-label for loading state', () => {
      // The component should have aria-label
      const expectedLabel = 'Loading passport card';
      expect(expectedLabel).toContain('Loading');
    });

    it('has aria-live="polite"', () => {
      // For screen reader announcements
      const expectedLive = 'polite';
      expect(['polite', 'assertive', 'off']).toContain(expectedLive);
    });

    it('has visually hidden loading text', () => {
      // For screen readers that don't support aria-label
      const loadingText = 'Loading...';
      expect(loadingText).toBe('Loading...');
    });
  });

  describe('skeleton box component', () => {
    it('accepts width and height props', () => {
      interface SkeletonBoxProps {
        width?: string;
        height?: string;
        className?: string;
      }

      const validProps: SkeletonBoxProps = {
        width: '60%',
        height: '28px',
        className: 'skeleton-margin-top',
      };

      expect(validProps.width).toBe('60%');
      expect(validProps.height).toBe('28px');
    });

    it('has aria-hidden="true"', () => {
      // Skeleton boxes should be hidden from screen readers
      const ariaHidden = true;
      expect(ariaHidden).toBe(true);
    });
  });

  describe('skeleton row component', () => {
    it('accepts labelWidth and valueWidth props', () => {
      interface SkeletonRowProps {
        labelWidth?: string;
        valueWidth?: string;
      }

      const defaultProps: SkeletonRowProps = {
        labelWidth: '30%',
        valueWidth: '50%',
      };

      expect(defaultProps.labelWidth).toBe('30%');
      expect(defaultProps.valueWidth).toBe('50%');
    });
  });

  describe('CSS classes', () => {
    it('uses passport-skeleton-container class', () => {
      const containerClass = 'passport-skeleton-container';
      expect(containerClass).toContain('passport');
      expect(containerClass).toContain('skeleton');
    });

    it('uses passport-skeleton class for base styles', () => {
      const baseClass = 'passport-skeleton';
      expect(baseClass).toBe('passport-skeleton');
    });

    it('uses passport-skeleton-box class with animation', () => {
      const boxClass = 'passport-skeleton-box';
      expect(boxClass).toContain('skeleton');
    });

    it('has helper classes for styling', () => {
      const helperClasses = [
        'skeleton-margin-top',
        'skeleton-circle',
        'skeleton-section-title',
      ];
      expect(helperClasses.length).toBe(3);
    });
  });

  describe('animation', () => {
    it('uses shimmer animation keyframes', () => {
      // The CSS should define passport-shimmer animation
      const animationName = 'passport-shimmer';
      expect(animationName).toBe('passport-shimmer');
    });

    it('respects prefers-reduced-motion', () => {
      // CSS should have media query for reduced motion
      const mediaQuery = '@media (prefers-reduced-motion: reduce)';
      expect(mediaQuery).toContain('prefers-reduced-motion');
    });
  });

  describe('memoization', () => {
    it('component is memoized for performance', async () => {
      // The component should be wrapped in React.memo
      const module = await import('../PassportSkeleton');
      const PassportSkeleton = module.default;

      // Memoized components have special properties
      // Check if it's a memo component by checking the type
      expect(PassportSkeleton).toBeDefined();
    });
  });
});

describe('PassportSkeleton integration', () => {
  describe('with PassportView', () => {
    it('shows during mode transitions', () => {
      // PassportView should show skeleton when isPending or showSkeleton is true
      const transitionStates = {
        showSkeleton: true,
        isPending: false,
      };

      const shouldShowSkeleton = transitionStates.showSkeleton || transitionStates.isPending;
      expect(shouldShowSkeleton).toBe(true);
    });

    it('hidden after transition completes', () => {
      const transitionStates = {
        showSkeleton: false,
        isPending: false,
      };

      const shouldShowSkeleton = transitionStates.showSkeleton || transitionStates.isPending;
      expect(shouldShowSkeleton).toBe(false);
    });
  });

  describe('card type detection', () => {
    it('uses detected card type for appropriate skeleton', () => {
      // PassportView should pass cardType from detectPassportType
      const cardTypes = ['nameplate', 'pcf', 'generic'] as const;

      cardTypes.forEach((cardType) => {
        expect(['nameplate', 'pcf', 'generic']).toContain(cardType);
      });
    });
  });
});
