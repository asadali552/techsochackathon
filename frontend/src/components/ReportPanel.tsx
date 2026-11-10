import { ArrowLeft, ArrowRight, Check, Clock3, Crosshair, FilePenLine, LoaderCircle, LockKeyhole, MapPin, Search, Send } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { categoryLabels, incidentStyle } from "../maps/evidence";
import { coordinates, places } from "../maps/places";
import { ApiError, requestIncidentAnalysis, submitIncident } from "../services/api";
import { canSignIn, signIn, type Session } from "../services/auth";
import type { Category, Coordinate, Incident, IncidentAnalysis, Mode } from "../types/api";

function localTime() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function ReportPanel({ mode, point, picking, session, onSession, onChoosePoint, onSearchPoint, onClearPoint }: {
  mode: Mode;
  point: Coordinate | null;
  picking: boolean;
  session: Session | null;
  onSession: (session: Session | null) => void;
  onChoosePoint: () => void;
  onSearchPoint: (point: Coordinate) => void;
  onClearPoint: () => void;
}) {
  const [category, setCategory] = useState<Category | "">("");
  const [description, setDescription] = useState("");
  const [occurred, setOccurred] = useState(localTime);
  const [busy, setBusy] = useState<"auth" | "report" | null>(null);
  const [error, setError] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [signInOpen, setSignInOpen] = useState(false);
  const [showTime, setShowTime] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [locationQuery, setLocationQuery] = useState("");
  const body = useRef<HTMLDivElement>(null);
  const [created, setCreated] = useState<Incident | null>(null);
  const pending = useRef<AbortController | null>(null);
  const analyzing = useRef<AbortController | null>(null);
  const [analysis, setAnalysis] = useState<IncidentAnalysis | null>(null);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisError, setAnalysisError] = useState("");

  useEffect(() => { body.current?.scrollTo(0, 0); }, [reviewing, created, signInOpen]);
  useEffect(() => {
    const viewport = window.visualViewport;
    const panel = body.current?.closest<HTMLElement>(".report-panel");
    if (!viewport || !panel) return;
    const resize = () => {
      const covered = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
      panel.style.setProperty("--report-keyboard", `${covered > 80 ? covered : 0}px`);
    };
    viewport.addEventListener("resize", resize);
    viewport.addEventListener("scroll", resize);
    return () => {
      viewport.removeEventListener("resize", resize);
      viewport.removeEventListener("scroll", resize);
      panel.style.removeProperty("--report-keyboard");
    };
  }, []);

  useEffect(() => () => {
    pending.current?.abort();
    analyzing.current?.abort();
  }, []);

  async function checkAnalysis(incidentId: string, token: string, start: boolean) {
    if (analyzing.current) return;
    const controller = new AbortController();
    analyzing.current = controller;
    setAnalysisError("");
    setAnalysisBusy(true);
    try {
      const result = await requestIncidentAnalysis(incidentId, token, start, controller.signal);
      if (!controller.signal.aborted) setAnalysis(result);
    } catch (failure) {
      if (!controller.signal.aborted) {
        setAnalysisError(failure instanceof ApiError && failure.status === 401
          ? "Sign in again to check AI analysis." : "Could not retrieve the AI analysis.");
      }
    } finally {
      if (!controller.signal.aborted) {
        analyzing.current = null;
        setAnalysisBusy(false);
      }
    }
  }

  function resetConfirmation() {
    analyzing.current?.abort();
    analyzing.current = null;
    setAnalysisBusy(false);
    setAnalysisError("");
    setAnalysis(null);
    setCreated(null);
  }

  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const form = new FormData(event.currentTarget);
    const controller = new AbortController();
    pending.current = controller;
    setError("");
    setBusy("auth");
    try {
      const next = await signIn(String(form.get("email")), String(form.get("password")), controller.signal);
      if (!controller.signal.aborted) {
        onSession(next);
        setSignInOpen(false);
      }
    } catch (failure) {
      if (!controller.signal.aborted) {
        setError(failure instanceof TypeError ? "Could not reach sign-in. Check your connection."
          : failure instanceof Error ? failure.message : "Sign-in failed.");
      }
    } finally {
      if (!controller.signal.aborted) {
        pending.current = null;
        setBusy(null);
      }
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    setError("");

    const summary = description.trim();
    const date = new Date(occurred);
    if (!category || !summary || summary.length > 2000 || summary.includes("\x00")) {
      setError("Select a category and enter a description between 1 and 2,000 characters.");
      return;
    }
    if (!point) {
      setError("Choose the report location on the map.");
      return;
    }
    if (Number.isNaN(date.getTime()) || date.getTime() > Date.now()) {
      setShowTime(true);
      setError("Choose an incident time at or before now.");
      return;
    }

    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    if (!reviewing) {
      setSearchOpen(false);
      setReviewing(true);
      return;
    }

    if (!session || session.expiresAt <= Date.now()) {
      onSession(null);
      setError("Your session expired. Sign in again to submit.");
      return;
    }
    const controller = new AbortController();
    pending.current = controller;
    setBusy("report");
    try {
      const report = await submitIncident({
        ...point, category, description: summary, occurred_at: date.toISOString(),
      }, session.token, controller.signal);
      if (!controller.signal.aborted) {
        setCreated(report);
        setReviewing(false);
        onClearPoint();
        setCategory("");
        setDescription("");
        setOccurred(localTime());
        setShowTime(false);
        setLocationQuery("");
        void checkAnalysis(report.id, session.token, true);
      }
    } catch (failure) {
      if (!controller.signal.aborted) {
        if (failure instanceof ApiError && failure.status === 401) onSession(null);
        setError(failure instanceof Error ? failure.message : "The report could not be submitted.");
      }
    } finally {
      if (!controller.signal.aborted) {
        pending.current = null;
        setBusy(null);
      }
    }
  }

  const reviewStatus = analysis?.review_status ?? created?.verification_status;
  const analysisMessage = analysisBusy ? "Analyzing report…"
    : analysisError || (analysis?.status === "processing" ? "Analysis in progress."
      : analysis?.status === "unavailable" ? "AI analysis is unavailable for this deployment."
      : analysis?.status === "failed" ? "AI analysis failed. Your report is saved."
      : analysis?.status === "completed" ? "AI suggestions are ready for human review."
      : "AI analysis is pending.");

  const showSignIn = !session && !created && (reviewing || signInOpen);
  const selectedPlace = point && places.find(({ latitude, longitude }) => point.latitude === latitude && point.longitude === longitude);
  const pointLabel = point && (selectedPlace?.name ?? `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}`);
  const query = locationQuery.trim().toLowerCase();
  const match = coordinates(query);
  const matches = query ? places.filter(({ name, detail }) => `${name} ${detail}`.toLowerCase().includes(query)) : places;
  const date = new Date(occurred);
  const displayTime = occurred && !Number.isNaN(+date) ? date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "Choose date and time";

  function selectLocation(next: Coordinate) {
    onSearchPoint(next);
    setSearchOpen(false);
    setLocationQuery("");
    setError("");
  }

  return (
    <section className="report-shell" aria-label="Report incident">
      <header className="panel-header">
        <div><span className="eyebrow"><FilePenLine size={13} /> Community reporting</span>
          <h2>{created ? "Report received" : reviewing ? "Review report" : showSignIn ? "Sign in" : "Report incident"}</h2></div>
        <a className="icon-button" href="#map" aria-label="Back to map" title="Back to map"><ArrowLeft size={19} /></a>
      </header>
      <div className="report-body" ref={body}>
        <div className="report-meta">
          {created ? <span className="badge status-pending">{reviewStatus === "pending" ? "Pending review" : "Report saved"}</span>
            : <span className="eyebrow">{reviewing ? "2 of 2 · Review" : showSignIn ? "Reporting account" : "1 of 2 · Details"}</span>}
          {mode === "demo" && <span className="badge demo">Fictional demo</span>}
        </div>
        {created ? (
          <div className="report-confirmation" role="status">
            <span className="confirm-icon"><Check size={22} /></span>
            <strong>Your report was saved.</strong>
            <p>{reviewStatus === "pending" ? "Pending review. Your report remains private until reviewed." : "Your report is in the review workflow."}</p>
            <p className="report-reference"><span>Report reference</span><code>{created.id}</code></p>
            <div className="report-review" aria-label="Private AI analysis">
              <span className="eyebrow">Private AI analysis</span>
              <p>{analysisMessage}</p>
              {analysis?.suggestion && <>
                <strong>{categoryLabels[analysis.suggestion.category]} · Provisional severity {analysis.suggestion.severity}/5</strong>
                <p dir="auto">{analysis.suggestion.summary}</p>
                <span className="muted">Human review status · {reviewStatus}</span>
              </>}
              {!analysisBusy && session && analysis?.status !== "completed" && (
                <button className="text-button" type="button"
                  onClick={() => void checkAnalysis(created.id, session.token, analysis?.status !== "processing")}>
                  {analysis?.status === "processing" ? "Check analysis status" : "Retry AI analysis"}
                </button>
              )}
            </div>
          </div>
        ) : reviewing ? (
          <>
            <form id="report-incident-form" className="report-review" onSubmit={submit} noValidate>
              <div className="report-review-heading">
                <strong>{category ? categoryLabels[category] : ""}</strong>
                <button className="text-button" type="button" disabled={busy !== null}
                  onClick={() => { setReviewing(false); setError(""); }}>Edit report</button>
              </div>
              <p dir="auto">{description.trim()}</p>
              <dl>
                <div><dt>When</dt><dd>{displayTime}</dd></div>
                <div><dt>Location</dt><dd>{pointLabel}</dd></div>
              </dl>
            </form>
            {session && <div className="account-line"><span className="badge status-verified">Signed in</span>
              <button className="text-button" type="button" disabled={busy !== null} onClick={() => { onSession(null); setError(""); }}>Sign out</button></div>}
          </>
        ) : !showSignIn && (
          <form id="report-incident-form" className="report-form" onSubmit={submit} noValidate>
            {mode === "demo" && <p className="muted">Use a fictional example for this rehearsal.</p>}
            <fieldset className="report-categories">
              <legend>Incident category</legend>
              <div className="report-category-grid">
                {Object.entries(categoryLabels).map(([value, label]) => {
                  const item = value as Category;
                  return <label className="report-category" key={item}>
                    <input className="sr-only" name="incident-category" type="radio" value={item} checked={category === item}
                      onChange={() => { setCategory(item); setError(""); }} />
                    <span aria-hidden="true" className="report-category-icon">{incidentStyle(item).glyph}</span>
                    <span>{label}</span>
                  </label>;
                })}
              </div>
            </fieldset>
            <label><span className="report-field-heading">Description <small id="report-character-count">{description.length.toLocaleString()} / 2,000</small></span>
              <textarea aria-label="Description" aria-describedby="report-character-count" dir="auto" required maxLength={2000} rows={3}
                value={description} onChange={(event) => { setDescription(event.target.value); setError(""); }}
                placeholder="What happened? Leave out names and personal details." />
            </label>
            <button className="report-time" type="button" aria-label="Change incident date and time" aria-expanded={showTime}
              onClick={() => setShowTime(!showTime)}><Clock3 size={16} /><span>When</span><strong>{displayTime}</strong></button>
            {showTime && <label>Incident date and time
              <input type="datetime-local" required max={localTime()} value={occurred}
                onChange={(event) => { setOccurred(event.target.value); setError(""); }} />
              <small className="muted">Uses your device time zone.</small>
            </label>}
            <div className="form-location">
              <strong>Report location</strong>
              {point && <div className="location-picked" role="status"><MapPin size={15} /><span><strong>Location selected</strong><small>{pointLabel}</small></span></div>}
              <div className="report-location-actions">
                <button className="secondary-button" type="button" onClick={onChoosePoint} aria-pressed={picking}>
                  <Crosshair size={16} />{point ? "Adjust pin" : "Choose location on map"}
                </button>
                <button className="secondary-button" type="button" aria-expanded={searchOpen} onClick={() => setSearchOpen(!searchOpen)}>
                  <Search size={15} /> Search location
                </button>
              </div>
              {searchOpen && <div className="report-location-search">
                <label className="sr-only" htmlFor="report-location-query">Search locations</label>
                <input id="report-location-query" type="search" autoComplete="off" value={locationQuery}
                  placeholder="Landmark or latitude, longitude" onChange={(event) => setLocationQuery(event.target.value)} />
                {match && <button type="button" onClick={() => selectLocation(match)}>Use these coordinates</button>}
                {matches.map((place) => <button type="button" key={place.name} onClick={() => selectLocation(place)}>
                  {place.name}<small>{place.detail}</small>
                </button>)}
                {!match && !matches.length && <p className="muted">Try a Multan landmark or choose a point on the map.</p>}
              </div>}
            </div>
          </form>
        )}
        {showSignIn && <div className="sign-in-card">
          <div className="sign-in-title"><LockKeyhole size={16} /><strong>Sign in required</strong></div>
          <p>{canSignIn ? "Use your registered account. Your draft stays here." : "Sign-in is unavailable until Supabase is configured."}</p>
          {canSignIn && <form id="report-sign-in" className="report-form" onSubmit={authenticate}>
            <label>Email<input type="email" name="email" autoComplete="username" required /></label>
            <label>Password<input type="password" name="password" autoComplete="current-password" required /></label>
          </form>}
          {!reviewing && <button className="text-button" type="button" disabled={busy !== null}
            onClick={() => { setSignInOpen(false); setError(""); }}>Back to draft</button>}
        </div>}
      </div>
      <footer className="report-footer">
        {error && <p className="form-error" role="alert">{error}</p>}
        {created ? <div className="report-footer-actions">
          <button className="text-button" type="button" onClick={resetConfirmation}>Report another incident</button>
          <a className="primary-button" href="#map">Return to map <ArrowRight size={16} /></a>
        </div> : <>
          <p className="report-privacy"><LockKeyhole size={14} />
            {reviewing ? "Reports start private. A configured AI provider receives redacted text for analysis."
              : session ? "Reports start private and are reviewed before publication." : "Sign-in is required to submit. Reports start private."}
          </p>
          {showSignIn ? <button className="primary-button" form="report-sign-in" type="submit" disabled={busy !== null || !canSignIn}>
            {busy === "auth" && <LoaderCircle size={16} className="spin" />} {busy === "auth" ? "Signing in…" : "Sign in"}
          </button> : <div className="report-footer-actions">
            {!reviewing && <button className="text-button" type="button" onClick={() => {
              if (session) onSession(null);
              else setSignInOpen(true);
              setError("");
            }}>{session ? "Sign out" : "Sign in"}</button>}
            <button className="primary-button" form="report-incident-form" type="submit" disabled={busy !== null}>
              {busy === "report" ? <LoaderCircle size={16} className="spin" /> : reviewing ? <Send size={16} /> : <ArrowRight size={16} />}
              {busy === "report" ? "Submitting…" : reviewing ? "Submit incident" : "Review report"}
            </button>
          </div>}
        </>}
      </footer>
    </section>
  );
}
