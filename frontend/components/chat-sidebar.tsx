"use client";

import { useEffect, useRef, useState } from "react";
import type { Conversation } from "./chat-app";

interface Props {
  conversations: Conversation[];
  currentId: string;
  open: boolean;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onStar: (id: string) => void;
  onToggle: () => void;
}

function groupByDate(convs: Conversation[]) {
  const starred = convs.filter((c) => c.starred);
  const rest = convs.filter((c) => !c.starred);

  const todayStart = new Date().setHours(0, 0, 0, 0);
  const yesterdayStart = todayStart - 86400000;
  const weekStart = todayStart - 7 * 86400000;

  const groups: { label: string; items: Conversation[] }[] = [];
  const push = (label: string, items: Conversation[]) => {
    if (items.length) groups.push({ label, items });
  };

  push("已收藏", starred);
  push("今天", rest.filter((c) => c.createdAt >= todayStart));
  push("昨天", rest.filter((c) => c.createdAt >= yesterdayStart && c.createdAt < todayStart));
  push("近 7 天", rest.filter((c) => c.createdAt >= weekStart && c.createdAt < yesterdayStart));
  push("更早", rest.filter((c) => c.createdAt < weekStart));
  return groups;
}

export default function ChatSidebar({
  conversations,
  currentId,
  open,
  onNew,
  onSelect,
  onDelete,
  onRename,
  onStar,
  onToggle,
}: Props) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpenId) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpenId]);

  function startRename(conv: Conversation) {
    setMenuOpenId(null);
    setRenamingId(conv.id);
    setRenameValue(conv.title);
  }

  function commitRename() {
    if (renamingId && renameValue.trim()) {
      onRename(renamingId, renameValue.trim());
    }
    setRenamingId(null);
  }

  if (!open) {
    return (
      <div className="flex w-12 shrink-0 flex-col items-center gap-2 border-r border-slate-200 bg-white py-3">
        <button onClick={onToggle} className="rounded-xl p-2 text-slate-500 hover:bg-slate-100" title="展開側欄">
          <MenuIcon />
        </button>
        <button onClick={onNew} className="rounded-xl p-2 text-teal-700 hover:bg-teal-50" title="新增諮詢">
          <PlusIcon />
        </button>
      </div>
    );
  }

  const groups = groupByDate(conversations);

  return (
    <aside className="flex w-64 shrink-0 flex-col overflow-hidden border-r border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <span className="text-sm font-bold text-slate-700">諮詢紀錄</span>
        <button onClick={onToggle} className="rounded-xl p-1.5 text-slate-500 hover:bg-slate-100" title="收合側欄">
          <MenuIcon />
        </button>
      </div>

      <div className="px-3 pb-1 pt-2">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-bold text-teal-700 transition hover:bg-teal-50"
        >
          <PlusIcon />
          新的諮詢
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {groups.length === 0 && (
          <p className="mt-8 text-center text-xs text-slate-400">目前沒有諮詢紀錄</p>
        )}
        {groups.map((group) => (
          <div key={group.label} className="mt-3">
            <p className="px-2 py-1 text-xs font-bold text-slate-400">{group.label}</p>
            {group.items.map((conv) => {
              const isActive = conv.id === currentId;
              const showMenu = hoveredId === conv.id || isActive;

              return (
                <div
                  key={conv.id}
                  onClick={() => {
                    if (renamingId !== conv.id) onSelect(conv.id);
                  }}
                  onMouseEnter={() => setHoveredId(conv.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  className={`relative flex cursor-pointer items-center rounded-xl px-3 py-2 text-sm transition ${
                    isActive ? "bg-teal-50 text-teal-800" : "text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  {conv.starred && <span className="mr-1 shrink-0 text-xs text-amber-400">★</span>}

                  {renamingId === conv.id ? (
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
                      className="min-w-0 flex-1 border-b border-teal-400 bg-transparent text-xs focus:outline-none"
                    />
                  ) : (
                    <span className="flex-1 truncate text-xs font-medium">{conv.title}</span>
                  )}

                  {showMenu && renamingId !== conv.id && (
                    <div
                      className="relative ml-1 shrink-0"
                      ref={menuOpenId === conv.id ? menuRef : undefined}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => setMenuOpenId(menuOpenId === conv.id ? null : conv.id)}
                        className="rounded-lg p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
                        title="更多操作"
                      >
                        <DotsIcon />
                      </button>

                      {menuOpenId === conv.id && (
                        <div className="absolute right-0 top-full z-50 mt-1 w-44 rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
                          <MenuItem
                            icon={<StarMenuIcon filled={!!conv.starred} />}
                            label={conv.starred ? "取消收藏" : "加入收藏"}
                            onClick={() => {
                              onStar(conv.id);
                              setMenuOpenId(null);
                            }}
                          />
                          <MenuItem icon={<RenameIcon />} label="重新命名" onClick={() => startRename(conv)} />
                          <div className="my-1 border-t border-slate-100" />
                          <MenuItem
                            icon={<TrashIcon />}
                            label="刪除"
                            onClick={() => {
                              onDelete(conv.id);
                              setMenuOpenId(null);
                            }}
                            danger
                          />
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
    </aside>
  );
}

function MenuItem({
  icon,
  label,
  onClick,
  danger,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-2.5 px-3 py-2 text-sm transition ${
        danger ? "text-red-500 hover:bg-red-50" : "text-slate-700 hover:bg-slate-50"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function DotsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <circle cx="5" cy="12" r="2" />
      <circle cx="12" cy="12" r="2" />
      <circle cx="19" cy="12" r="2" />
    </svg>
  );
}

function StarMenuIcon({ filled }: { filled: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
      <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
    </svg>
  );
}

function RenameIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3,6 5,6 21,6" />
      <path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6" />
      <path d="M8,6V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2" />
    </svg>
  );
}
