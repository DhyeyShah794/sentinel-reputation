"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Target,
  Search,
  Brain,
  Radio,
  Layers,
  Shield,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Executive Overview", icon: LayoutDashboard },
  { href: "/command-center", label: "Command Center", icon: Target },
  { href: "/explorer", label: "Content Explorer", icon: Search },
  { href: "/intelligence", label: "Intelligence Hub", icon: Brain },
  { href: "/sources", label: "Source Analysis", icon: Radio },
  { href: "/themes", label: "Theme Explorer", icon: Layers },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className="fixed left-0 top-0 bottom-0 bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col z-50 transition-[width] duration-300 ease-in-out overflow-hidden"
      style={{ width: collapsed ? "4rem" : "16rem" }}
    >
      {/* Logo */}
      <div className="px-3 border-b border-[var(--border)] flex items-center min-h-[64px]">
        <div className={`flex items-center gap-3 min-w-0 ${collapsed ? "w-full justify-center" : ""}`}>
          <div className="w-9 h-9 flex-shrink-0 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden">
              <h1 className="text-base font-bold gradient-text tracking-tight whitespace-nowrap">
                SENTINEL
              </h1>
              <p className="text-[10px] text-[var(--text-muted)] tracking-widest uppercase whitespace-nowrap">
                Reputation Intelligence
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Toggle row */}
      <div className="px-2 py-2 border-b border-[var(--border)]">
        <button
          onClick={onToggle}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={`flex items-center w-full rounded-md px-2 py-1.5 text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors cursor-pointer ${
            collapsed ? "justify-center" : "justify-end"
          }`}
        >
          {collapsed ? (
            <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <ChevronLeft className="w-3.5 h-3.5" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto overflow-x-hidden">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              className={`nav-link flex items-center gap-3 px-2.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                collapsed ? "justify-center" : ""
              } ${isActive ? "active" : "text-[var(--text-secondary)]"}`}
            >
              <Icon className="w-4.5 h-4.5 flex-shrink-0" />
              {!collapsed && (
                <span className="whitespace-nowrap overflow-hidden text-ellipsis">
                  {item.label}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Brand Footer */}
      {!collapsed && (
        <div className="px-4 pt-3 pb-2 border-t border-[var(--border)]">
          <div className="text-xs text-[var(--text-muted)]">
            <p className="font-medium text-[var(--text-secondary)]">
              ICICI Prudential AMC
            </p>
            <p className="mt-0.5">Jul 2025 – Mar 2026</p>
          </div>
          <div className="mt-2 text-[10px] text-[var(--text-muted)]">
            Built for{" "}
            <span className="text-[var(--text-secondary)]">
              Eminence Strategy
            </span>
          </div>
        </div>
      )}

    </aside>
  );
}
