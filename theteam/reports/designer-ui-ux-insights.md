# Design Reviewer: UI/UX Insights for Agentic Awareness Monitoring

**Author:** Designer (Design Reviewer)  
**Date:** 2026-09-21  
**Context:** theteam discussion on agentic-friendly, scalable awareness cycle

---

## Current State Assessment

The system has two UI layers:
- **Terminal UI** (`theteam/ui/terminal_ui.py`): curses-based, tabbed, real-time
- **Web Dashboard** (`theteam/ui/web_dashboard/theteam_dashboard/`): Reflex-based, metric cards
- **CLI Monitor** (`scripts/sa_runner.py:cmd_monitor()`): raw ASCII text output

**Problem:** The current UI presents system awareness as static snapshots, not as a living agentic surface. The critical 0.00/1.0 health score is visible, but the system's autonomous responses (circuit breaker trips, self-corrections, recovery attempts) are invisible to the user.

---

## Top 5 UI/UX Approaches for Agentic-Friendly Awareness Monitoring

### 1. Real-time Agency Signaling
Visualize the system's autonomous actions as a temporal flow:
- Circuit breaker state transitions (closed → half-open → open)
- Self-correction attempts and outcomes
- Agent contributions and recovery actions

**Current gap:** `dashboard.py` shows `critical_folders_ok` as a binary badge; no visibility into *why* it's OK or what's being done about it.

**Design:** An activity timeline component that renders agency events as they happen, with visual differentiation between automated actions and human interventions.

### 2. Progressive Disclosure of Complexity
Surface the critical health score prominently, but allow drill-down into the 4-phase analysis breakdown:
- Structure Analysis
- Documentation Audit
- Architecture Review
- Infrastructure Assessment

**Current gap:** The web dashboard's metric cards are flat — no hierarchical depth to investigate failures.

**Design:** Expandable metric cards with phase-level detail, collapsible by default, with severity indicators (healthy/warning/critical) at each level.

### 3. Circuit Breaker Visual Semantics
The `circuit_breaker` state machine (closed/half-open/open) needs intuitive visual language:
- **Closed:** Green, normal operation
- **Half-open:** Amber, testing recovery
- **Open:** Red, system protected

**Current gap:** State only appears as text in `cmd_monitor()` output; no visual urgency or animation.

**Design:** Animated state indicator with pulse on transitions, accompanied by contextual messaging about what the system is doing to recover.

### 4. Agent Contribution Visibility
The `.loop-state.json` tracks `team_members` and `team_contributions`, but neither UI exposes this. An agentic-friendly dashboard should show:
- Which agents are active
- What they're working on
- Contribution history and success rates

**Current gap:** No agent-level visibility in any UI layer.

**Design:** Agent roster panel with status indicators (active/idle/offline), recent contribution feed, and per-agent performance metrics.

### 5. Self-Stabilization Feedback Loops
When the system detects drift or partial outputs (via `self_check_loop_state()`), the UI should show:
- The correction attempt
- The outcome
- Whether the system reached an acceptable state

**Current gap:** Self-check results only appear as terminal text; no persistent visibility or follow-up tracking.

**Design:** A "System Health Journey" view that shows the timeline of detected issues, correction attempts, and resolution status — demonstrating agency and building trust.

---

## Most Impactful Improvement

**Add a real-time activity stream to the web dashboard** that visualizes the system's autonomous actions. This directly addresses the critical 0.00/1.0 health state by making the system's response to problems visible and understandable.

**Specific implementation:** Create a new `ActivityStream` component in the Reflex dashboard that:
1. Reads from `.loop-state.json` and `system-awareness-ledger.json`
2. Polls for changes (or uses WebSocket if available)
3. Renders agency events (circuit breaker trips, self-corrections, agent contributions) as a chronological feed
4. Color-codes by severity and type
5. Provides drill-down into individual events

**Files to modify:**
- `theteam/ui/web_dashboard/theteam_dashboard/pages/dashboard.py` — add activity stream card
- `theteam/ui/web_dashboard/theteam_dashboard/state.py` — add activity data loading
- `scripts/sa_runner.py` — emit structured activity events (already partially done via `cmd_monitor()`)

---

## Edge Cases & Concerns

1. **Event loss during high-frequency updates:** The activity stream must buffer and batch events to avoid UI flooding. Use a sliding window (last 50 events) with load-more capability.

2. **State synchronization:** The `.loop-state.json` is written by `loop_state.py` and read by the dashboard. Ensure atomic writes (write to temp file, then rename) to prevent partial reads.

3. **Circuit breaker animation performance:** CSS animations on state transitions must be performant (use `transform`/`opacity`, not `width`/`height`).

4. **Accessibility:** Color alone should not convey state — use icons and text labels alongside color coding.

5. **Mobile responsiveness:** The dashboard must collapse to a single-column layout on small screens, prioritizing the health score and activity stream.