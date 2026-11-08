import QSiteProof.Basic

/-!
# Report: human-readable details and the certificate record

`detail` strings are explanatory only; the pass flags, result and blocking obligation
come from `check` / `verdict` / `blocking` in `QSiteProof.Basic`, which the theorems cover.
`lean/certify.py` has a Python mirror that must produce byte-identical output.
-/

namespace QSiteProof

def pad (width : Nat) (n : Nat) : String :=
  let s := toString n
  String.ofList (List.replicate (width - s.length) '0') ++ s

/-- kW as MW with 3 decimals, e.g. 150000 -> "150.000 MW". -/
def fmtMW (kw : Nat) : String := s!"{kw / 1000}.{pad 3 (kw % 1000)} MW"

/-- per-mille as percent with 1 decimal, e.g. 711 -> "71.1%". -/
def fmtPct (pm : Nat) : String := s!"{pm / 10}.{pm % 10}%"

/-- 1e-4 pu as pu with 4 decimals, e.g. 9937 -> "0.9937". -/
def fmtPu (v : Nat) : String := s!"{v / 10000}.{pad 4 (v % 10000)}"

def firstDup : List String → Option String
  | [] => none
  | x :: xs => if x ∈ xs then some x else firstDup xs

def upliftNote (e : Evidence) : String :=
  if effUplift e > 0 then s!" (+{fmtPct (effUplift e)} DLR headroom uplift)" else ""

def capacityDetail (e : Evidence) : String :=
  let sum := splitSum e.splits
  if sum ≠ e.requestedKw then
    s!"splits sum {fmtMW sum} != requested {fmtMW e.requestedKw}"
  else match firstDup (e.splits.map Split.id) with
  | some d => s!"substation {d} appears in more than one split"
  | none =>
    match e.splits.find? (fun s => !decide (SplitFits e s)) with
    | some s =>
      if s.known then
        s!"{s.id} split {fmtMW s.kw} > headroom {fmtMW s.headroomKw}{upliftNote e}"
      else s!"{s.id} has no headroom evidence in the grid snapshot"
    | none =>
      s!"{e.splits.length} splits sum to requested {fmtMW e.requestedKw}; every split <= substation headroom{upliftNote e}"

def thermalDetail (e : Evidence) : String :=
  if e.converged = false then "base-case power flow did not converge"
  else if e.hasLoading = false then "max line loading missing from physics result"
  else if e.maxLoadingPermille > e.loadingLimitPermille then
    s!"max loading {fmtPct e.maxLoadingPermille} > limit {fmtPct e.loadingLimitPermille}"
  else if e.hasVoltage = false then "voltage missing from physics result"
  else if e.vMinPu4 < e.vLoPu4 then s!"v_min {fmtPu e.vMinPu4} pu < {fmtPu e.vLoPu4} pu"
  else if e.vMaxPu4 > e.vHiPu4 then s!"v_max {fmtPu e.vMaxPu4} pu > {fmtPu e.vHiPu4} pu"
  else s!"converged; max loading {fmtPct e.maxLoadingPermille} <= {fmtPct e.loadingLimitPermille}; voltage {fmtPu e.vMinPu4}-{fmtPu e.vMaxPu4} pu within {fmtPu e.vLoPu4}-{fmtPu e.vHiPu4} pu"

def n1Detail (e : Evidence) : String :=
  let first := if e.firstViolation = "" then "" else s!"; first: {e.firstViolation}"
  if e.n1Pass = false then s!"N-1 contingency check failed ({e.violationCount} violations{first})"
  else if e.violationCount > 0 then s!"{e.violationCount} violations reported{first}"
  else "N-1 pass; no violations"

def flexDetail (e : Evidence) : String :=
  if e.storageKw > e.committedStorageKw then
    s!"storage {fmtMW e.storageKw} > committed {fmtMW e.committedStorageKw} ({e.commitmentSource})"
  else if e.curtailmentKw > e.committedCurtailmentKw then
    s!"curtailment {fmtMW e.curtailmentKw} > committed {fmtMW e.committedCurtailmentKw} ({e.commitmentSource})"
  else
    s!"storage {fmtMW e.storageKw} <= {fmtMW e.committedStorageKw}; curtailment {fmtMW e.curtailmentKw} <= {fmtMW e.committedCurtailmentKw} ({e.commitmentSource})"

/-- (name, used, lead days) for each flex option with a lead time. -/
def leadOptions (e : Evidence) : List (String × Bool × Nat) :=
  [("DLR", e.dlr, e.leadDlrDays), ("storage", decide (0 < e.storageKw), e.leadStorageDays),
   ("reconductor", e.reconductor, e.leadReconductorDays)]

def deadlineDetail (e : Evidence) : String :=
  if e.asOfDay > e.deadlineDay then s!"as-of {e.asOfDate} is after deadline {e.deadlineDate}"
  else
    let left := e.deadlineDay - e.asOfDay
    let used := (leadOptions e).filter (fun x => x.2.1)
    match used.find? (fun x => decide (x.2.2 > left)) with
    | some (n, _, lead) =>
      s!"{n} lead time {lead} d (ASSUMED) > {left} d left before deadline {e.deadlineDate} (as of {e.asOfDate})"
    | none =>
      if used.isEmpty then
        s!"no flex option with a lead time used; {left} d left before deadline {e.deadlineDate} (as of {e.asOfDate})"
      else
        let names := ", ".intercalate (used.map (fun x => s!"{x.1} {x.2.2} d"))
        s!"used options finish in time ({names}; lead times ASSUMED) <= {left} d left before deadline {e.deadlineDate} (as of {e.asOfDate})"

def permitDetail (e : Evidence) : String :=
  let what := if e.reconductor then "reconductor" else "new ROW"
  if e.reconductor || e.newRow then
    if e.rowPermitGranted then s!"{what} used; ROW/permit granted per supplied evidence"
    else s!"{what} needs ROW/permit; no permit-granted evidence supplied"
  else "no reconductor or new ROW used; no ROW permit needed"

def penaltyDetail (e : Evidence) : String :=
  if e.requestedKw * e.curtailCapPermille < e.curtailmentKw * 1000 then
    s!"penalty trigger TRUE: curtailment {fmtMW e.curtailmentKw} > cap {fmtPct e.curtailCapPermille} of requested"
  else if ¬ decide (DeadlineMet e) then "penalty trigger TRUE: deadline miss"
  else s!"penalty trigger FALSE: curtailment {fmtMW e.curtailmentKw} <= cap {fmtPct e.curtailCapPermille} of requested; deadline met"

def detail : Obligation → Evidence → String
  | .capacity, e => capacityDetail e
  | .thermalVoltage, e => thermalDetail e
  | .n1, e => n1Detail e
  | .flexCommitment, e => flexDetail e
  | .deadline, e => deadlineDetail e
  | .permitRow, e => permitDetail e
  | .penaltyTrigger, e => penaltyDetail e

structure CheckRow where
  name : String
  pass : Bool
  detail : String
  deriving Repr, DecidableEq

structure Report where
  checks : List CheckRow
  result : Verdict
  blocking : Option String
  deriving Repr, DecidableEq

def report (e : Evidence) : Report where
  checks := order.map (fun o => ⟨o.name, check o e, detail o e⟩)
  result := verdict e
  blocking := (blocking e).map (fun o => s!"{o.name}: {detail o e}")

/-- Determinism: the certificate is a pure function of the evidence. -/
theorem certify_deterministic {e₁ e₂ : Evidence} (h : e₁ = e₂) : report e₁ = report e₂ := by
  rw [h]

theorem report_result_eq_verdict (e : Evidence) : (report e).result = verdict e := rfl

/-- Each reported pass flag is exactly the decision of its obligation. -/
theorem report_pass_sound (e : Evidence) :
    ∀ r ∈ (report e).checks, ∃ o, r.name = o.name ∧ (r.pass = true ↔ Holds o e) := by
  intro r hr
  simp only [report, List.mem_map] at hr
  obtain ⟨o, _, rfl⟩ := hr
  exact ⟨o, rfl, check_iff o e⟩

/-- A reported GREEN means every encoded obligation holds; RED names a violated one. -/
theorem report_green_iff_all (e : Evidence) : (report e).result = .green ↔ ∀ o, Holds o e :=
  verdict_green_iff_all e

theorem report_blocking_none_iff_green (e : Evidence) :
    (report e).blocking = none ↔ (report e).result = .green := by
  simp only [report, Option.map_eq_none_iff]
  unfold verdict blocking
  cases firstFailing e <;> simp

end QSiteProof
