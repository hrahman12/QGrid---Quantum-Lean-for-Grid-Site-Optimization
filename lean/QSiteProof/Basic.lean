/-!
# QSiteProof obligations

Decidable obligations over a plan + evidence record, in fixed-point natural numbers
(no floats): power in kW, line loading in per-mille of rating, voltage in 1e-4 pu,
dates as day numbers since 1970-01-01, ratios in per-mille.

The Python side (`lean/certify.py`) converts plan / physics / site / snapshot into this
record, rounding every value in the conservative direction (headroom and v_min down,
loading, v_max, storage and curtailment up).

Scope: a GREEN verdict means only that every obligation below holds for the supplied
evidence. It is not a utility interconnection approval. Hard/negotiable tags and the AMBER
verdict are composed from these pass flags in `lean/certify.py` (`_verdict`), not here.
-/

namespace QSiteProof

/-- One substation split of the requested load. -/
structure Split where
  id : String
  kw : Nat
  /-- net load after storage / curtailment relief (quantum/load_model.py net_split, rounded up) -/
  netKw : Nat
  /-- false when the snapshot has no headroom for this substation -/
  known : Bool
  headroomKw : Nat
  deriving Repr

/-- Gross kW on the feeders that share one transformer bank, and that bank's cap. -/
structure Bank where
  id : String
  kw : Nat
  capKnown : Bool
  capKw : Nat
  deriving Repr

/-- N-1 firm headroom for the split at the same position in `splits`. -/
structure Firm where
  id : String
  known : Bool
  firmKw : Nat
  deriving Repr

/-- Everything the checker sees; built by `build_evidence` in `lean/certify.py` (JSON keys are snake_case). -/
structure Evidence where
  requestedKw : Nat
  splits : List Split
  banks : List Bank
  firm : List Firm
  /-- plan site_id is empty or equals the site id (computed by the Python evidence builder) -/
  planSiteBound : Bool
  dlr : Bool
  dlrHeadroomUpliftPermille : Nat
  storageKw : Nat
  curtailmentKw : Nat
  reconductor : Bool
  newRow : Bool
  converged : Bool
  hasLoading : Bool
  maxLoadingPermille : Nat
  loadingLimitPermille : Nat
  hasVoltage : Bool
  vMinPu4 : Nat
  vMaxPu4 : Nat
  vLoPu4 : Nat
  vHiPu4 : Nat
  n1Pass : Bool
  violationCount : Nat
  firstViolation : String
  committedStorageKw : Nat
  committedCurtailmentKw : Nat
  commitmentSource : String
  asOfDay : Nat
  deadlineDay : Nat
  asOfDate : String
  deadlineDate : String
  leadDlrDays : Nat
  leadStorageDays : Nat
  leadReconductorDays : Nat
  rowPermitGranted : Bool
  curtailCapPermille : Nat
  deriving Repr

/-! ## Obligations (as propositions) -/

/-- DLR headroom uplift that applies to this plan (0 when DLR is not used). -/
def effUplift (e : Evidence) : Nat := if e.dlr then e.dlrHeadroomUpliftPermille else 0

def splitSum : List Split → Nat
  | [] => 0
  | s :: ss => s.kw + splitSum ss

/-- No substation id appears twice (so per-split headroom checks cannot be split around). -/
def Distinct : List String → Prop
  | [] => True
  | x :: xs => x ∉ xs ∧ Distinct xs

instance decDistinct : (l : List String) → Decidable (Distinct l)
  | [] => isTrue trivial
  | x :: xs =>
    have := decDistinct xs
    inferInstanceAs (Decidable (x ∉ xs ∧ Distinct xs))

/-- net split <= substation headroom (DLR uplifts lines only, not transformer headroom). -/
def SplitFits (_e : Evidence) (s : Split) : Prop :=
  s.known = true ∧ s.netKw ≤ s.headroomKw

instance (e : Evidence) (s : Split) : Decidable (SplitFits e s) := by
  unfold SplitFits; infer_instance

/-- capacity: splits sum exactly to the request, ids distinct, each split within headroom. -/
def CapacityOk (e : Evidence) : Prop :=
  splitSum e.splits = e.requestedKw ∧ Distinct (e.splits.map Split.id) ∧
    ∀ s ∈ e.splits, SplitFits e s

instance (e : Evidence) : Decidable (CapacityOk e) := by unfold CapacityOk; infer_instance

/-- thermal / voltage: converged base case, loading within limit, voltage inside band. -/
def ThermalVoltageOk (e : Evidence) : Prop :=
  e.converged = true ∧ e.hasLoading = true ∧ e.maxLoadingPermille ≤ e.loadingLimitPermille ∧
    e.hasVoltage = true ∧ e.vLoPu4 ≤ e.vMinPu4 ∧ e.vMaxPu4 ≤ e.vHiPu4

instance (e : Evidence) : Decidable (ThermalVoltageOk e) := by
  unfold ThermalVoltageOk; infer_instance

/-- N-1: contingency analysis passed and no violation was reported at all. -/
def N1Ok (e : Evidence) : Prop := e.n1Pass = true ∧ e.violationCount = 0

instance (e : Evidence) : Decidable (N1Ok e) := by unfold N1Ok; infer_instance

/-- flexibility commitment: storage / curtailment used within what the site committed. -/
def FlexOk (e : Evidence) : Prop :=
  e.storageKw ≤ e.committedStorageKw ∧ e.curtailmentKw ≤ e.committedCurtailmentKw

instance (e : Evidence) : Decidable (FlexOk e) := by unfold FlexOk; infer_instance

/-- deadline: not already past, and every used flex option's lead time ends by the deadline. -/
def DeadlineMet (e : Evidence) : Prop :=
  e.asOfDay ≤ e.deadlineDay ∧
    (e.dlr = true → e.asOfDay + e.leadDlrDays ≤ e.deadlineDay) ∧
    (0 < e.storageKw → e.asOfDay + e.leadStorageDays ≤ e.deadlineDay) ∧
    (e.reconductor = true → e.asOfDay + e.leadReconductorDays ≤ e.deadlineDay)

instance (e : Evidence) : Decidable (DeadlineMet e) := by unfold DeadlineMet; infer_instance

/-- permit / ROW: reconductoring or a new ROW needs permit-granted evidence. -/
def PermitOk (e : Evidence) : Prop :=
  (e.reconductor = true ∨ e.newRow = true) → e.rowPermitGranted = true

instance (e : Evidence) : Decidable (PermitOk e) := by unfold PermitOk; infer_instance

/-- penalty trigger: curtailment above the cap (share of request) or a deadline miss. -/
def PenaltyTriggered (e : Evidence) : Prop :=
  e.requestedKw * e.curtailCapPermille < e.curtailmentKw * 1000 ∨ ¬ DeadlineMet e

instance (e : Evidence) : Decidable (PenaltyTriggered e) := by
  unfold PenaltyTriggered; infer_instance

/-- bank: every shared transformer bank has a known cap and its feeders' MW stay within it. -/
def BankOk (e : Evidence) : Prop := ∀ b ∈ e.banks, b.capKnown = true ∧ b.kw ≤ b.capKw

instance (e : Evidence) : Decidable (BankOk e) := by unfold BankOk; infer_instance

/-- storage relief: storage + curtailment cannot exceed the requested load. -/
def StorageReliefOk (e : Evidence) : Prop := e.storageKw + e.curtailmentKw ≤ e.requestedKw

instance (e : Evidence) : Decidable (StorageReliefOk e) := by
  unfold StorageReliefOk; infer_instance

/-- A split with known firm headroom and nonzero load has net kW within that firm headroom. -/
def FirmFits (p : Split × Firm) : Prop := p.2.known = true → p.1.kw ≠ 0 → p.1.netKw ≤ p.2.firmKw

instance (p : Split × Firm) : Decidable (FirmFits p) := by unfold FirmFits; infer_instance

/-- firm N-1: every split's net kW <= its N-1 firm headroom, where known. -/
def FirmN1Ok (e : Evidence) : Prop := ∀ p ∈ e.splits.zip e.firm, FirmFits p

instance (e : Evidence) : Decidable (FirmN1Ok e) := by unfold FirmN1Ok; infer_instance

/-- evidence binding: the plan names this site (or no site). -/
def EvidenceBound (e : Evidence) : Prop := e.planSiteBound = true

instance (e : Evidence) : Decidable (EvidenceBound e) := by
  unfold EvidenceBound; infer_instance

/-! ## Obligations, fixed order, verdict -/

inductive Obligation where
  | capacity | thermalVoltage | n1 | flexCommitment | deadline | permitRow | penaltyTrigger
  | bank | storageRelief | firmN1 | evidenceBinding
  deriving DecidableEq, Repr

def Obligation.name : Obligation → String
  | .capacity => "capacity"
  | .thermalVoltage => "thermal_voltage"
  | .n1 => "n1"
  | .flexCommitment => "flex_commitment"
  | .deadline => "deadline"
  | .permitRow => "permit_row"
  | .penaltyTrigger => "penalty_trigger"
  | .bank => "bank"
  | .storageRelief => "storage_relief"
  | .firmN1 => "firm_n1"
  | .evidenceBinding => "evidence_binding"

/-- What it means for obligation `o` to hold on evidence `e`. -/
def Holds : Obligation → Evidence → Prop
  | .capacity, e => CapacityOk e
  | .thermalVoltage, e => ThermalVoltageOk e
  | .n1, e => N1Ok e
  | .flexCommitment, e => FlexOk e
  | .deadline, e => DeadlineMet e
  | .permitRow, e => PermitOk e
  | .penaltyTrigger, e => ¬ PenaltyTriggered e
  | .bank, e => BankOk e
  | .storageRelief, e => StorageReliefOk e
  | .firmN1, e => FirmN1Ok e
  | .evidenceBinding, e => EvidenceBound e

instance (o : Obligation) (e : Evidence) : Decidable (Holds o e) := by
  cases o <;> unfold Holds <;> infer_instance

/-- The fixed check order; the first failing one is the blocking condition. -/
def order : List Obligation :=
  [.capacity, .thermalVoltage, .n1, .flexCommitment, .deadline, .permitRow, .penaltyTrigger,
   .bank, .storageRelief, .firmN1, .evidenceBinding]

theorem order_complete (o : Obligation) : o ∈ order := by
  cases o <;> simp [order]

/-- The decision procedure for one obligation. -/
def check (o : Obligation) (e : Evidence) : Bool := decide (Holds o e)

theorem check_iff (o : Obligation) (e : Evidence) : check o e = true ↔ Holds o e := by
  simp [check]

def firstFailing (e : Evidence) : Option Obligation := order.find? (fun o => !check o e)

/-- The blocking condition: first failing obligation in `order`, if any. -/
def blocking (e : Evidence) : Option Obligation := firstFailing e

inductive Verdict where
  | green | red
  deriving DecidableEq, Repr

def verdict (e : Evidence) : Verdict :=
  match firstFailing e with
  | none => .green
  | some _ => .red

/-! ## Theorems -/

theorem firstFailing_none_iff (e : Evidence) : firstFailing e = none ↔ ∀ o, Holds o e := by
  unfold firstFailing
  rw [List.find?_eq_none]
  constructor
  · intro h o
    have := h o (order_complete o)
    simpa [check] using this
  · intro h o _
    simp [check, h o]

/-- GREEN iff every encoded obligation holds. -/
theorem verdict_green_iff_all (e : Evidence) : verdict e = .green ↔ ∀ o, Holds o e := by
  rw [← firstFailing_none_iff]
  unfold verdict
  cases firstFailing e <;> simp

/-- The named blocking obligation is in fact violated. -/
theorem blocking_violated {e : Evidence} {o : Obligation} (h : blocking e = some o) :
    ¬ Holds o e := by
  have := List.find?_some h
  simpa [check] using this

/-- RED -> there is a blocking obligation and it is violated. -/
theorem verdict_red_blocking_sound (e : Evidence) (h : verdict e = .red) :
    ∃ o, blocking e = some o ∧ ¬ Holds o e := by
  unfold verdict at h
  cases hb : firstFailing e with
  | none => simp [hb] at h
  | some o => exact ⟨o, hb, blocking_violated hb⟩

/-- RED iff some obligation fails. -/
theorem verdict_red_iff_exists (e : Evidence) : verdict e = .red ↔ ∃ o, ¬ Holds o e := by
  constructor
  · intro h
    obtain ⟨o, _, ho⟩ := verdict_red_blocking_sound e h
    exact ⟨o, ho⟩
  · intro ⟨o, ho⟩
    cases hv : verdict e with
    | red => rfl
    | green => exact absurd ((verdict_green_iff_all e).mp hv o) ho

/-- The blocking obligation is the FIRST failure: every obligation before it in `order` holds. -/
theorem blocking_is_first {e : Evidence} {o : Obligation} (h : blocking e = some o) :
    ∃ pre post, order = pre ++ o :: post ∧ ∀ o' ∈ pre, Holds o' e := by
  unfold blocking firstFailing at h
  rw [List.find?_eq_some_iff_append] at h
  obtain ⟨_, pre, post, hsplit, hpre⟩ := h
  refine ⟨pre, post, hsplit, fun o' ho' => ?_⟩
  have := hpre o' ho'
  simpa [check] using this

/-- The verdict and blocking condition depend only on which obligations hold. -/
theorem firstFailing_ext {e₁ e₂ : Evidence} (h : ∀ o, Holds o e₁ ↔ Holds o e₂) :
    firstFailing e₁ = firstFailing e₂ := by
  have hf : (fun o => !check o e₁) = (fun o => !check o e₂) := by
    funext o
    show (!decide (Holds o e₁)) = !decide (Holds o e₂)
    rw [decide_eq_decide.mpr (h o)]
  unfold firstFailing
  rw [hf]

theorem verdict_extensional {e₁ e₂ : Evidence} (h : ∀ o, Holds o e₁ ↔ Holds o e₂) :
    verdict e₁ = verdict e₂ ∧ blocking e₁ = blocking e₂ := by
  have := firstFailing_ext h
  exact ⟨by unfold verdict; rw [this], this⟩

end QSiteProof
