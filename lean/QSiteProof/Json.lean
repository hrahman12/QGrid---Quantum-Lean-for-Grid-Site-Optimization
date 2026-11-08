import Lean.Data.Json
import QSiteProof.Report

/-!
# Evidence JSON in, certificate JSON out (uses `Lean.Json`)
-/

namespace QSiteProof
open Lean

def parseSplit (j : Json) : Except String Split := do
  return {
    id := ← j.getObjValAs? String "substation_id"
    kw := ← j.getObjValAs? Nat "kw"
    netKw := ← j.getObjValAs? Nat "net_kw"
    known := ← j.getObjValAs? Bool "headroom_known"
    headroomKw := ← j.getObjValAs? Nat "headroom_kw" }

def parseBank (j : Json) : Except String Bank := do
  return {
    id := ← j.getObjValAs? String "bank_id"
    kw := ← j.getObjValAs? Nat "kw"
    capKnown := ← j.getObjValAs? Bool "cap_known"
    capKw := ← j.getObjValAs? Nat "cap_kw" }

def parseFirm (j : Json) : Except String Firm := do
  return {
    id := ← j.getObjValAs? String "substation_id"
    known := ← j.getObjValAs? Bool "firm_known"
    firmKw := ← j.getObjValAs? Nat "firm_kw" }

def parseEvidence (j : Json) : Except String Evidence := do
  let fmt ← j.getObjValAs? String "format"
  if fmt != "qsiteproof-evidence/1" then throw s!"unsupported evidence format {fmt}"
  let splitsJ ← j.getObjValAs? (Array Json) "splits"
  let splits ← splitsJ.toList.mapM parseSplit
  let banks ← (← j.getObjValAs? (Array Json) "banks").toList.mapM parseBank
  let firm ← (← j.getObjValAs? (Array Json) "firm").toList.mapM parseFirm
  let n (k : String) : Except String Nat := j.getObjValAs? Nat k
  let b (k : String) : Except String Bool := j.getObjValAs? Bool k
  let s (k : String) : Except String String := j.getObjValAs? String k
  return {
    requestedKw := ← n "requested_kw", splits, banks, firm
    planSiteBound := ← b "plan_site_bound"
    dlr := ← b "dlr", dlrHeadroomUpliftPermille := ← n "dlr_headroom_uplift_permille"
    storageKw := ← n "storage_kw", curtailmentKw := ← n "curtailment_kw"
    reconductor := ← b "reconductor", newRow := ← b "new_row"
    converged := ← b "converged", hasLoading := ← b "has_loading"
    maxLoadingPermille := ← n "max_loading_permille", loadingLimitPermille := ← n "loading_limit_permille"
    hasVoltage := ← b "has_voltage", vMinPu4 := ← n "v_min_pu4", vMaxPu4 := ← n "v_max_pu4"
    vLoPu4 := ← n "v_lo_pu4", vHiPu4 := ← n "v_hi_pu4"
    n1Pass := ← b "n1_pass", violationCount := ← n "violation_count", firstViolation := ← s "first_violation"
    committedStorageKw := ← n "committed_storage_kw", committedCurtailmentKw := ← n "committed_curtailment_kw"
    commitmentSource := ← s "commitment_source"
    asOfDay := ← n "as_of_day", deadlineDay := ← n "deadline_day"
    asOfDate := ← s "as_of", deadlineDate := ← s "deadline"
    leadDlrDays := ← n "lead_dlr_days", leadStorageDays := ← n "lead_storage_days"
    leadReconductorDays := ← n "lead_reconductor_days"
    rowPermitGranted := ← b "row_permit_granted", curtailCapPermille := ← n "curtail_cap_permille" }

def Verdict.toString : Verdict → String
  | .green => "GREEN"
  | .red => "RED"

def reportJson (r : Report) : Json :=
  Json.mkObj [
    ("engine", Json.str "lean4"),
    ("lean_version", Json.str Lean.versionString),
    ("checks", Json.arr (r.checks.map (fun c =>
      Json.mkObj [("name", Json.str c.name), ("pass", Json.bool c.pass), ("detail", Json.str c.detail)])).toArray),
    ("result", Json.str r.result.toString),
    ("blocking_condition", match r.blocking with | some s => Json.str s | none => Json.null)]

def runText (text : String) : Except String Json := do
  let j ← Json.parse text
  let e ← parseEvidence j
  return reportJson (report e)

end QSiteProof
