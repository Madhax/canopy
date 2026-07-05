import { useCallback, useEffect, useRef, useState } from "react";
import type { OrganizationDoc } from "../schema/organization";
import { ApiError } from "../api/client";
import { saveOrganization } from "../api/organizations";
import { useDocumentStore, useTemporalStore } from "../store/documentStore";

export type SaveStatus = "saved" | "saving" | "unsaved" | "failed" | "conflict";

const sig = (doc: OrganizationDoc) => JSON.stringify({ ...doc, updatedAt: null });
const rescueKey = (id: string) => `canopy:rescue:${id}`;

/** Debounced autosave of the whole top-level document, with conflict + crash-rescue (docs §7.6). */
export function useAutosave(doc: OrganizationDoc | null) {
  const [status, setStatus] = useState<SaveStatus>("saved");
  const savedSig = useRef<string | null>(null);
  const retry = useRef(0);
  const setUpdatedAt = useDocumentStore((s) => s.setUpdatedAt);

  // Initialize the saved signature the first time a document loads.
  useEffect(() => {
    if (doc && savedSig.current === null) savedSig.current = sig(doc);
  }, [doc]);

  const doSave = useCallback(async () => {
    const current = useDocumentStore.getState().doc;
    if (!current) return;
    setStatus("saving");
    try {
      const result = await saveOrganization(current);
      // Bump updatedAt to the server value WITHOUT creating an undo entry.
      useTemporalStore.getState().pause();
      setUpdatedAt(result.document.updatedAt ?? current.updatedAt ?? null);
      useTemporalStore.getState().resume();
      savedSig.current = sig(current);
      retry.current = 0;
      // If the user kept editing during the save, we're already dirty again.
      setStatus(sig(useDocumentStore.getState().doc!) === savedSig.current ? "saved" : "unsaved");
      sessionStorage.removeItem(rescueKey(current.id));
    } catch (err) {
      if (err instanceof ApiError && err.code === "STALE_WRITE") {
        setStatus("conflict");
        return;
      }
      setStatus("failed");
      retry.current += 1;
      const backoff = Math.min(1000 * 2 ** retry.current, 15000);
      setTimeout(() => void doSave(), backoff);
    }
  }, [setUpdatedAt]);

  // Watch for dirtiness and debounce a save.
  useEffect(() => {
    if (!doc || savedSig.current === null) return;
    if (sig(doc) === savedSig.current) return;
    setStatus((s) => (s === "conflict" ? s : "unsaved"));
    sessionStorage.setItem(rescueKey(doc.id), JSON.stringify(doc));
    const handle = setTimeout(() => void doSave(), 1000);
    return () => clearTimeout(handle);
  }, [doc, doSave]);

  // Warn on unload while there are unsaved edits.
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (status === "unsaved" || status === "saving") {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [status]);

  const saveNow = useCallback(() => void doSave(), [doSave]);

  const overwriteMine = useCallback(
    async (serverUpdatedAt: string | null) => {
      // Adopt the server's updatedAt so the concurrency check passes, then re-save our content.
      useTemporalStore.getState().pause();
      setUpdatedAt(serverUpdatedAt);
      useTemporalStore.getState().resume();
      savedSig.current = null; // force re-dirty
      await doSave();
    },
    [doSave, setUpdatedAt],
  );

  const markSavedSignature = useCallback((d: OrganizationDoc) => {
    savedSig.current = sig(d);
    setStatus("saved");
  }, []);

  return { status, saveNow, overwriteMine, markSavedSignature };
}
