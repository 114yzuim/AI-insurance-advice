"use client";

import { useState, useEffect, useRef } from "react";
import type { TranslateRecord } from "./translate-app";

interface Props {
  records: TranslateRecord[];
  currentId: string;
  open: boolean;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onStar: (id: string) => void;
  onToggle: () => void;
}

function groupByDate(records: TranslateRecord[]) {
  const starred = records.filter((r) => r.starred);
  const rest = records.filter((r) => !r.starred);
  const todayStart = new Date().setHours(0, 0, 0, 0);
  const yesterdayStart = todayStart - 86400000;
  const weekStart = todayStart - 7 * 86400000;
  const groups: { label: string; items: TranslateRecord[] }[] = [];
  const push = (label: string, items: TranslateRecord[]) => {
    if (items.length) groups.push({ label, items });
  };
  push("最愛", starred);
  push("今天", rest.filter((r) => r.createdAt >= todayStart));
  push("昨天", rest.filter((r) => r.createdAt >= yesterdayStart && r.createdAt < todayStart));
  push("過去 7 天", rest.filter((r) => r.createdAt >= weekStart && r.createdAt < yesterdayStart));
  push("更早", rest.filter((r) => r.createdAt < weekStart));
  return groups;
}

export default function TranslateSidebar({
  records, currentId, open, onNew, onSelect, onDelete, onRename, onStar, onToggle,
}: Props) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpenId) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node))
        setMenuOpenId(null);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpenId]);

  function startRename(rec: TranslateRecord) {
    setMenuOpenId(null);
    setRenamingId(rec.id);
    setRenameValue(rec.title);
  }

  function commitRename() {
    if (renamingId && renameValue.trim()) onRename(renamingId, renameValue.trim());
    setRenamingId(null);
  }

  if (!open) {
    return (
      <div className="flex flex-col w-12 shrink-0 border-r border-gray-200 bg-white items-center py-3 gap-2">
        <button onClick={onToggle} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"><MenuIcon /></button>
        <button onClick={onNew} className="p-2 rounded-lg hover:bg-blue-50 text-blue-700"><PlusIcon /></button>
      </div>
    );
  }

  const groups = groupByDate(records);

  return (
    <div className="flex flex-col w-64 shrink-0 border-r border-gray-200 bg-white overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <span className="font-semibold text-sm text-gray-700">翻譯記錄</span>
        <button onClick={onToggle} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500"><MenuIcon /></button>
      </div>

      <div className="px-3 pt-2 pb-1">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-blue-700 hover:bg-blue-50 transition-colors"
        >
          <PlusIcon />
          新翻譯
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {groups.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-8">尚無翻譯記錄</p>
        )}
        {groups.map((group) => (
          <div key={group.label} className="mt-3">
            <p className="text-xs text-gray-400 px-2 py-1 font-medium">{group.label}</p>
            {group.items.map((rec) => {
              const isActive = rec.id === currentId;
              const showMenu = hoveredId === rec.id || isActive;
              return (
                <div
                  key={rec.id}
                  onClick={() => { if (renamingId !== rec.id) onSelect(rec.id); }}
                  onMouseEnter={() => setHoveredId(rec.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  className={`relative flex items-center rounded-lg px-3 py-2 text-sm cursor-pointer transition-colors ${
                    isActive ? "bg-blue-50 text-blue-700" : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  {rec.starred && <span className="mr-1 text-yellow-400 text-xs shrink-0">★</span>}

                  {renamingId === rec.id ? (
                    <input
                      autoFocus
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onBlur={commitRename}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename();
                        if (e.key === "Escape") setRenamingId(null);
                        e.stopPropagation();
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="flex-1 text-xs bg-transparent border-b border-blue-400 focus:outline-none min-w-0"
                    />
                  ) : (
                    <span className="truncate flex-1 text-xs">{rec.title}</span>
                  )}

                  {showMenu && renamingId !== rec.id && (
                    <div
                      className="relative shrink-0 ml-1"
                      ref={menuOpenId === rec.id ? menuRef : undefined}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => setMenuOpenId(menuOpenId === rec.id ? null : rec.id)}
                        className="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600"
                      >
                        <DotsIcon />
                      </button>
                      {menuOpenId === rec.id && (
                        <div className="absolute right-0 top-full mt-1 w-40 bg-white border border-gray-200 rounded-xl shadow-lg z-50 py-1">
                          <MenuItem icon={<StarIcon filled={!!rec.starred} />} label={rec.starred ? "取消最愛" : "加入最愛"} onClick={() => { onStar(rec.id); setMenuOpenId(null); }} />
                          <MenuItem icon={<RenameIcon />} label="重新命名" onClick={() => startRename(rec)} />
                          <div className="border-t border-gray-100 my-1" />
                          <MenuItem icon={<TrashIcon />} label="刪除" onClick={() => { onDelete(rec.id); setMenuOpenId(null); }} danger />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function MenuItem({ icon, label, onClick, danger }: { icon: React.ReactNode; label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button onClick={onClick} className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors ${danger ? "text-red-500 hover:bg-red-50" : "text-gray-700 hover:bg-gray-50"}`}>
      {icon}{label}
    </button>
  );
}

function MenuIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></svg>;
}
function PlusIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>;
}
function DotsIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" /></svg>;
}
function StarIcon({ filled }: { filled: boolean }) {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2"><polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" /></svg>;
}
function RenameIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>;
}
function TrashIcon() {
  return <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3,6 5,6 21,6" /><path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6" /><path d="M8,6V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2" /></svg>;
}
