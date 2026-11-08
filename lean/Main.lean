import QSiteProof

/-- `qsiteproof <evidence.json>` (or `-` for stdin) prints the certificate JSON. -/
def main (args : List String) : IO UInt32 := do
  let text ← match args with
    | ["-"] => (← IO.getStdin).readToEnd
    | [path] => IO.FS.readFile path
    | _ => do
      IO.eprintln "usage: qsiteproof <evidence.json | ->"
      return 2
  match QSiteProof.runText text with
  | .ok j => IO.println j.compress; return 0
  | .error err => IO.eprintln s!"evidence error: {err}"; return 3
