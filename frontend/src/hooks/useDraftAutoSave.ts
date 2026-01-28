/**
 * Hook for auto-saving form drafts and preventing data loss.
 *
 * Features:
 * - Auto-saves to localStorage every AUTO_SAVE_INTERVAL_MS when form is dirty
 * - beforeunload warning when navigating away with unsaved changes
 * - Draft recovery on page load
 */

import { useEffect, useCallback, useRef } from 'react';
import { UseFormReturn } from 'react-hook-form';
import localforage from 'localforage';
import type { SubmodelFormData } from '../types/aas-elements';

/** Auto-save interval in milliseconds */
const AUTO_SAVE_INTERVAL_MS = 30000; // 30 seconds

/** Maximum draft age in milliseconds before expiration */
const DRAFT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

/** Draft storage key prefix */
const DRAFT_KEY_PREFIX = 'draft:';

interface DraftData {
  data: SubmodelFormData;
  timestamp: number;
  templateName: string;
  templateVersion?: string | null;
}

interface UseDraftAutoSaveOptions {
  /** The template name (used as storage key) */
  templateName: string;
  /** Optional template version */
  templateVersion?: string | null;
  /** Whether auto-save is enabled */
  enabled?: boolean;
}

interface UseDraftAutoSaveReturn {
  /** Check if a draft exists */
  hasDraft: () => Promise<boolean>;
  /** Load draft data */
  loadDraft: () => Promise<DraftData | null>;
  /** Clear saved draft */
  clearDraft: () => Promise<void>;
  /** Manually save draft */
  saveDraft: () => Promise<void>;
  /** Get draft age in human-readable format */
  getDraftAge: (timestamp: number) => string;
}

/**
 * Generate storage key for draft.
 */
function getDraftKey(templateName: string, templateVersion?: string | null): string {
  const versionSuffix = templateVersion ? `@${templateVersion}` : '';
  return `${DRAFT_KEY_PREFIX}${templateName}${versionSuffix}`;
}

/**
 * Format draft age for display.
 */
function formatDraftAge(timestamp: number): string {
  const ageMs = Date.now() - timestamp;
  const minutes = Math.floor(ageMs / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days} day${days > 1 ? 's' : ''} ago`;
  if (hours > 0) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  if (minutes > 0) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
  return 'just now';
}

/**
 * Hook for auto-saving form drafts and preventing data loss.
 */
export function useDraftAutoSave(
  form: UseFormReturn<SubmodelFormData>,
  options: UseDraftAutoSaveOptions
): UseDraftAutoSaveReturn {
  const { templateName, templateVersion, enabled = true } = options;
  const draftKey = getDraftKey(templateName, templateVersion);
  const lastSaveRef = useRef<number>(0);

  // Save draft to storage
  const saveDraft = useCallback(async () => {
    if (!enabled || !templateName) return;

    const data = form.getValues();
    const draft: DraftData = {
      data,
      timestamp: Date.now(),
      templateName,
      templateVersion,
    };

    try {
      await localforage.setItem(draftKey, draft);
      lastSaveRef.current = Date.now();
    } catch (err) {
      console.warn('Failed to save draft:', err);
    }
  }, [enabled, templateName, templateVersion, draftKey, form]);

  // Check if draft exists
  const hasDraft = useCallback(async (): Promise<boolean> => {
    try {
      const draft = await localforage.getItem<DraftData>(draftKey);
      if (!draft) return false;

      // Check if draft is expired
      if (Date.now() - draft.timestamp > DRAFT_MAX_AGE_MS) {
        await localforage.removeItem(draftKey);
        return false;
      }

      return true;
    } catch {
      return false;
    }
  }, [draftKey]);

  // Load draft data
  const loadDraft = useCallback(async (): Promise<DraftData | null> => {
    try {
      const draft = await localforage.getItem<DraftData>(draftKey);
      if (!draft) return null;

      // Check if draft is expired
      if (Date.now() - draft.timestamp > DRAFT_MAX_AGE_MS) {
        await localforage.removeItem(draftKey);
        return null;
      }

      return draft;
    } catch {
      return null;
    }
  }, [draftKey]);

  // Clear saved draft
  const clearDraft = useCallback(async (): Promise<void> => {
    try {
      await localforage.removeItem(draftKey);
    } catch (err) {
      console.warn('Failed to clear draft:', err);
    }
  }, [draftKey]);

  // Get draft age in human-readable format
  const getDraftAge = useCallback((timestamp: number): string => {
    return formatDraftAge(timestamp);
  }, []);

  // Auto-save effect
  useEffect(() => {
    if (!enabled) return;

    const interval = setInterval(() => {
      const { isDirty } = form.formState;
      if (isDirty) {
        saveDraft();
      }
    }, AUTO_SAVE_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [enabled, form, saveDraft]);

  // Navigation guard effect (beforeunload)
  useEffect(() => {
    if (!enabled) return;

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      const { isDirty } = form.formState;
      if (isDirty) {
        e.preventDefault();
        // Modern browsers require returnValue to be set
        e.returnValue = '';
        return '';
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [enabled, form.formState]);

  return {
    hasDraft,
    loadDraft,
    clearDraft,
    saveDraft,
    getDraftAge,
  };
}

export default useDraftAutoSave;
