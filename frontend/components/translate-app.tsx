"use client";

import { useState, useEffect } from "react";
import TranslateSidebar from "./translate-sidebar";
import TranslateContent from "./translate-page";

export interface TranslateRecord {
  id: string;
  title: string;
  createdAt: number;
  summary: string;
  disclaimer: string;
  starred?: boolean;
}

const STORAGE_KEY = "translate_records";

export default function TranslateApp({
  initPdfUrl,
  initProductName,
}: {
  initPdfUrl: string;
  initProductName: string;
}) {
  const [records, setRecords] = useState<TranslateRecord[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [initialized, setInitialized] = useState(false);
  // stored as state so "新翻譯" doesn't re-trigger the original URL
  const [pendingUrl, setPendingUrl] = useState(initPdfUrl);
  const [pendingName, setPendingName] = useState(initProductName);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const parsed: TranslateRecord[] = JSON.parse(raw);
        setRecords(parsed);
        if (!initPdfUrl && parsed.length > 0) {
          setCurrentId(parsed[0].id);
        }
      } catch {}
    }
    setInitialized(true);
  }, []);

  // only save after initial load — prevents overwriting stored data with []
  useEffect(() => {
    if (!initialized) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
  }, [records, initialized]);

  function handleSave(record: TranslateRecord) {
    setPendingUrl("");   // consume — won't trigger again on next "新翻譯"
    setPendingName("");
    setRecords((prev) => [record, ...prev.filter((r) => r.id !== record.id)]);
    setCurrentId(record.id);
  }

  function handleDelete(id: string) {
    const next = records.filter((r) => r.id !== id);
    setRecords(next);
    if (currentId === id) setCurrentId(next.length > 0 ? next[0].id : null);
  }

  function handleRename(id: string, title: string) {
    setRecords((prev) => prev.map((r) => (r.id === id ? { ...r, title } : r)));
  }

  function handleStar(id: string) {
    setRecords((prev) => prev.map((r) => (r.id === id ? { ...r, starred: !r.starred } : r)));
  }

  const current = records.find((r) => r.id === currentId) ?? null;

  return (
    <div className="flex h-full overflow-hidden bg-gray-50">
      <TranslateSidebar
        records={records}
        currentId={currentId ?? ""}
        open={sidebarOpen}
        onNew={() => setCurrentId(null)}
        onSelect={setCurrentId}
        onDelete={handleDelete}
        onRename={handleRename}
        onStar={handleStar}
        onToggle={() => setSidebarOpen((v) => !v)}
      />
      <TranslateContent
        key={currentId ?? "new"}
        record={current}
        initPdfUrl={currentId ? "" : pendingUrl}
        initProductName={currentId ? "" : pendingName}
        onSave={handleSave}
      />
    </div>
  );
}
