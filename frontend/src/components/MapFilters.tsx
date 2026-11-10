import { ChevronDown, Layers } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { categoryLabels, verificationLabels } from "../maps/evidence";
import type { Category, Verification } from "../types/api";

export type Filters = { category: Category | ""; verification: Verification | ""; start: string; end: string };
export const emptyFilters: Filters = { category: "", verification: "", start: "", end: "" };

export function MapFilters({ filters, setFilters, invalidDates, modified, children }: {
  filters: Filters;
  setFilters: (filters: Filters) => void;
  invalidDates: boolean;
  modified?: boolean;
  children: ReactNode;
}) {
  const menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const dismiss = (event: PointerEvent) => {
      const element = menu.current;
      if (element?.open && event.target instanceof Node && !element.contains(event.target)) element.open = false;
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, []);
  return (
    <details ref={menu} className="layer-menu" onKeyDown={(event) => {
      if (event.key === "Escape") { event.currentTarget.open = false; event.currentTarget.querySelector("summary")?.focus(); }
    }}>
      <summary aria-description={modified ? "Layers or filters adjusted" : undefined}><Layers size={17} /> Layers
        {modified && <span className="layer-modified" aria-hidden="true" title="Layers or filters adjusted" />}
        <ChevronDown size={13} />
      </summary>
      <div className="filter-popover floating">
        <p className="eyebrow">Map layers</p>
        <div className="layer-options">{children}</div>
        <div className="filter-fields">
          <p className="eyebrow">Report filters</p>
          <label>Category<select aria-label="Incident category" value={filters.category} onChange={(event) => setFilters({ ...filters, category: event.target.value as Filters["category"] })}>
            <option value="">All categories</option>
            {Object.entries(categoryLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select></label>
          <label>Verification<select aria-label="Verification status" value={filters.verification} onChange={(event) => setFilters({ ...filters, verification: event.target.value as Filters["verification"] })}>
            <option value="">All statuses</option>
            {Object.entries(verificationLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
          </select></label>
        </div>
        <div className="filter-fields">
          <p className="eyebrow">Date range <small>Device time</small></p>
          <label>From<input type="datetime-local" value={filters.start} onChange={(event) => setFilters({ ...filters, start: event.target.value })} /></label>
          <label>Until<input type="datetime-local" value={filters.end} onChange={(event) => setFilters({ ...filters, end: event.target.value })} /></label>
          {invalidDates && <p className="form-error" role="alert">Choose an end time after the start.</p>}
          {(filters.start || filters.end) && <button className="text-button" type="button" onClick={() => setFilters({ ...filters, start: "", end: "" })}>Clear dates</button>}
        </div>
      </div>
    </details>
  );
}
