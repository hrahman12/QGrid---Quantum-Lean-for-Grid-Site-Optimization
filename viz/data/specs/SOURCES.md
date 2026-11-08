# Equipment specs: sources (data/specs/)

Every number in `equipment_specs.json` is either **SOURCED** (quoted from a document listed below, with the table, page or figure named) or **ASSUMED** (labelled, with the reason). Unit conversions are done in code and marked as conversions. Nothing here is a PG&E or Silicon Valley Power rating, a utility study or an approval. Where a drawing is marked 'Not to Scale', only its labelled dimensions are used; nothing is measured off the drawing.

Built 2026-11-08. Leaves: **263**, SOURCED **223**, ASSUMED **40**.

## Where the numbers come from

| Key | Document | URL |
|---|---|---|
| `GO95_T1` | CPUC General Order 95, Table 1: Basic Minimum Allowable Vertical Clearance of Wires above ... Ground ... (and notes kk, ll) | https://ia.cpuc.ca.gov/gos/GO95/go_95_table_1.html |
| `GO95_T2` | CPUC General Order 95, Table 2: Basic Minimum Allowable Clearance of Wires from Other Wires (and notes ff, gg, hh) | https://ia.cpuc.ca.gov/gos/GO95/go_95_table_2.html |
| `GO95_R37` | CPUC General Order 95, Rule 37 (Table 1 basis: 60 F, no wind; allowed reductions for temperature/loading) | https://ia.cpuc.ca.gov/gos/GO95/go_95_rule_37.html |
| `GO95_R38` | CPUC General Order 95, Rule 38 (Table 2 basis: 60 F, no wind; max 10% reduction) | https://ia.cpuc.ca.gov/gos/GO95/go_95_rule_38.html |
| `PSB_DEIR` | CPUC, Power the South Bay Project (A.24-05-014) Draft EIR, June 2025, Ch. 2 Project Description (Newark-NRS 230 kV, LS Power Grid California). Overhead segment crosses San Jose RWF ponds at Alviso. | https://ia.cpuc.ca.gov/environment/info/esa/psb/pdfs/Power_the_South_Bay_DEIR_June2025_508_ADA.pdf |
| `PSB_IDX` | CPUC Power the South Bay project page | https://ia.cpuc.ca.gov/environment/info/esa/psb/index.html |
| `NORTECH` | CPUC Negative Declaration, PG&E Nortech Substation and Kifer-Nortech / Trimble-Nortech 115 kV lines (North San Jose) | https://ia.cpuc.ca.gov/Environment/Info/esa/nortech/nortech_negdec.htm |
| `NESJ` | CPUC Northeast San Jose Transmission Reinforcement (Los Esteros Substation) project description | https://ia.cpuc.ca.gov/Environment/info/aspen/nesanjo/description.html |
| `JM_CH2` | PG&E Jefferson-Martin 230 kV Final PEA, Chapter 2 Project Description, Table 2-5 Summary of Project Facilities (pp. 2-58 to 2-60) | https://ia.cpuc.ca.gov/Environment/info/aspen/jefferson_martin/pdf/002.pdf |
| `JM_F27` | Jefferson-Martin PEA Figure 2-7, Typical Heavy Angle Lattice Steel Tower (not to scale) | https://ia.cpuc.ca.gov/Environment/info/aspen/jefferson_martin/pdf/2-7%20TYP1.PDF |
| `JM_F28` | Jefferson-Martin PEA Figure 2-8, Typical Tangent Lattice Steel Tower (not to scale; labelled dims) | https://ia.cpuc.ca.gov/Environment/info/aspen/jefferson_martin/pdf/2-8%20TypTangent%20Steel%20Tower.pdf |
| `JM_F29` | Jefferson-Martin PEA Figure 2-9, Typical Tangent Tubular Steel Pole (not to scale; labelled dims) | https://ia.cpuc.ca.gov/Environment/info/aspen/jefferson_martin/pdf/2-9%20TypTangent%20Steel%20Pole.pdf |
| `TRIVALLEY` | CPUC, PG&E Tri-Valley 2002 Capacity Increase project description, Table 1 Summary of Project Facilities | https://ia.cpuc.ca.gov/Environment/info/aspen/tri-valley/projdesc.pdf |
| `VASONA` | CPUC Initial Study, PG&E Vasona Substation (Los Gatos, Santa Clara County), 230/12 kV | https://ia.cpuc.ca.gov/environment/info/esa/vasona/vasona_initial.htm |
| `HOLLISTER` | CPUC IS/MND (A.09-11-016) PG&E Hollister 115 kV Power Line Reconductoring, Ch. 2, Summary of Project Components + Table 2-2 | https://ia.cpuc.ca.gov/Environment/info/esa/hollister/dmnd/2_Project_Description.pdf |
| `SW80100` | Southwire SPEC 80100 ACSR, table 'Weights, Measurements, Electrical and Engineering Data' (rev 1.000.022, Oct 2026) | https://cabletechsupport.southwire.com/tile/23/spec/80100/?country=US |
| `PRYSMIAN` | Prysmian (Colombia) ACSR datasheet, ASTM sizes; ampacity footnote: sun + wind 0.61 m/s, 25 C ambient, 75 C conductor, 1033.3 W/m2, emissivity = absorptivity = 0.5, sea level | https://co.prysmian.com/sites/co.prysmian.com/files/media/documents/04%20ACSR%20ALUMINIUM%20CONDUCTOR%20STEEL%20REINFORCED_0.pdf |
| `IEEE738` | Singh et al., 'Sensitivity Analysis of Dynamic Line Rating for ACSR Conductors using IEEE-738', arXiv 2607.23536, Table I (parameters taken from IEEE Std 738-2023 [ref 2]) | https://arxiv.org/abs/2607.23536 |
| `WIKI_INS` | Wikipedia 'Insulator (electricity)', table 'Typical number of disc insulator units for standard line voltages', citing Diesendorf, Insulation Coordination in High Voltage Power Systems (Butterworth, 1974) | https://en.wikipedia.org/wiki/Insulator_(electricity) |
| `YOJIU` | Yojiu Electric, ANSI C29.2 52-series suspension insulator dimension table | https://www.yojiuelec.com/52-series-ball-socket-and-clevis-tongue-type-product |
| `VICTOR` | Victor Insulators toughened-glass suspension, VI 52-3H TG | https://www.victorinsulators.com/products/transmission-products/glass-suspensions/ |
| `HUBBELL_QSIL` | Hubbell Quadri*Sil polymer suspension catalog (Jan 2019), p. 3-36 Corona Performance | https://hubbellcdn.com/catalogfull/CA08051E_Insulators_QSilSuspension.pdf |
| `DOE_LPT` | US DOE OE/ISER, Large Power Transformers and the U.S. Electric Grid (Apr 2014), Table 2 'Estimated Magnitude of LPTs in 2011' (source: NERC Spare Equipment Database 2011) | https://www.energy.gov/sites/prod/files/2014/04/f15/LPTStudyUpdate-040914.pdf |
| `WEG_LISTING` | Surplus Record listing JVT-3879: WEG 2017 substation transformer 30/40/50/56 MVA ONAN/ONAF, 115 kV delta / 12.47Y kV (a real unit's nameplate data, secondary-market listing) | https://surplusrecord.com/listing/30-56-mva-115000-delta-primary-12470y-secondary-weg-2017-280984/ |
| `PJM` | PJM TSDS Technical Requirements Section III, Substation Bus Configurations and Design Requirements (5/20/2002 text, 2016 markup) | https://pjm.com/-/media/committees-groups/subcommittees/dedss/20160719/20160719-pjm-ts-std-sec-3.ashx |
| `CEC_APP` | CEC Docket 19-SPPE-04, Microsoft San Jose City Data Center (SJC02) SPPE Application TN 230741, Sections 2.1-2.2, Figs 2-3a, 2-6, Land Use p. on height | https://efiling.energy.ca.gov/getdocument.aspx?tn=230741 |
| `CEC_ORDER` | CEC Docket 19-SPPE-04 TN 232773, Notice of Committee Conference (project summary) | https://efiling.energy.ca.gov/getdocument.aspx?tn=232773 |
| `CEC_PAGE` | CEC project page, San Jose Data Center (99 MW, exempted) | https://www.energy.ca.gov/powerplant/reciprocating-engine/san-jose-data-center |

### Sources tried but not read

- RUS Bulletin 1724E-300 (Design Guide for Rural Substations): https://www.rd.usda.gov/files/UEP_Bulletin_1724E-300.pdf -> HTTP 403. Values that would have come from it are ASSUMED.
- Silicon Valley Power published documents (Northern-Kifer 115 kV IS/MND etc.): https://www.siliconvalleypower.com/home/showpublisheddocument/... -> HTTP 403. Values that would have come from it are ASSUMED.
- Hubbell Hi-Lite porcelain catalog: https://hubbellcdn.com/catalogfull/CA08051E_Insulators_HiLiteSuspension.pdf -> HTTP 404. Values that would have come from it are ASSUMED.

## Drawing rules for the 3D scene

- Local first: the 230 kV tubular steel poles of the Power the South Bay line (heights 90 to 150 ft, Fig. 2-4 and Table 2-2) are near the site, on the San Jose RWF ponds at Alviso. The 115 kV poles come from the CPUC Nortech filing (North San Jose). These two are the best-matched geometry.
- 115 kV lattice towers come from a PG&E Central Coast line (Hollister IS/MND), because no North San Jose 115 kV lattice dimensions were found.
- Crossarm and arm lengths, phase spacing on structures, lattice base width, substation bus phase spacing and bus heights are **not published** in any document read. The JSON gives a **floor derived from GO 95** (the minimum clearance plus the PG&E insulator-string length and an assumed 35 degree swing), marked ASSUMED.
- A 500 kV structure is not drawn. No 500 kV facility lies within the 25 km radius.
- 60 kV wood-pole height is a placeholder (ASSUMED), because the SVP documents were blocked (HTTP 403).

## Cross-check (230 kV TSP height)

Ground clearance at maximum sag is 0.9 x 30 ft = 8.2 m (GO 95 Table 1 Case 4 with the Rule 37 10% allowance; PG&E designs to 30 to 32 ft). Add an assumed sag of about 8 m for a 900 ft ruling span at high temperature, two arm gaps of about 6 m each (GO 95 vertical separation of 3.10 m plus the 2.56 m string), one 2.56 m string, and about 3 m of OPGW peak. That sums to about 34 m (111 ft), inside the sourced 100 to 120 ft (Jefferson-Martin Fig. 2-9) and 90 to 105 ft (PSB tangent) ranges. So the derived floors agree with the filed heights. The sag value is illustrative and comes from no source.

## Every value

| Path | Value | Status | Source detail / reason |
|---|---|---|---|
| `structures.230kV_tubular_steel_pole_PSB_local._what` | Self-supported tubular steel poles (TSPs), delta conductor configuration on tangents, vertical on dead-ends, two OPGW. 11 structures NN-5..NN-15 span SCVWD land and San Jose RWF drying ponds (Alviso), ~1.9 mi; 4 more NN-1..NN-4 at Newark. | SOURCED | Sec. 2.6.1.1 Overhead Transmission Line, p. 2-14 |
| `structures.230kV_tubular_steel_pole_PSB_local.tangent_height_m` | 32.004 | SOURCED | Fig. 2-4 'Tangent Pole NNAC-M-TAN01' labelled 90'-105'; Table 2-2 max 150 ft |
| `structures.230kV_tubular_steel_pole_PSB_local.angle_height_m` | 36.576 | SOURCED | Fig. 2-4 'Angle Pole NNAC-M-ANG15' 120'; Table 2-2 max 150 ft |
| `structures.230kV_tubular_steel_pole_PSB_local.deadend_height_m` | 42.672 | SOURCED | Fig. 2-4 'Deadend Pole NNAC-M-VD' 140'; Table 2-2 max 135 ft (table and figure differ; figure value used) |
| `structures.230kV_tubular_steel_pole_PSB_local.cable_riser_height_m` | 33.528 | SOURCED | Fig. 2-4 'Cable Pole NNAC-M-TRNS' 110'; Table 2-2 Cable Riser max 140 ft |
| `structures.230kV_tubular_steel_pole_PSB_local.switch_pole_height_m` | 39.624 | SOURCED | Table 2-2 Tubular Steel Switch Pole 130 ft |
| `structures.230kV_tubular_steel_pole_PSB_local.three_pole_deadend_height_m` | 22.86 | SOURCED | Fig. 2-4 '3-Pole Structure NNAC-3P-DE30' 65'-75' |
| `structures.230kV_tubular_steel_pole_PSB_local.substation_termination_riser_height_m` | 7.62 | SOURCED | Sec 2.6.1: 230 kV AC termination/riser structures 'approximately 25 feet tall' |
| `structures.230kV_tubular_steel_pole_PSB_local.tangent_base_diameter_m` | 1.829 | SOURCED | Table 2-2: Tangent avg base diameter at grade 6 ft, tip 14 in |
| `structures.230kV_tubular_steel_pole_PSB_local.tangent_tip_diameter_m` | 0.3556 | SOURCED | Table 2-2: 14 in |
| `structures.230kV_tubular_steel_pole_PSB_local.angle_base_diameter_m` | 2.438 | SOURCED | Table 2-2: Angle 8 ft base, 14 in tip |
| `structures.230kV_tubular_steel_pole_PSB_local.deadend_base_diameter_m` | 2.438 | SOURCED | Table 2-2: Dead-End 8 ft base, 32 in tip |
| `structures.230kV_tubular_steel_pole_PSB_local.deadend_tip_diameter_m` | 0.8128 | SOURCED | Table 2-2: 32 in |
| `structures.230kV_tubular_steel_pole_PSB_local.riser_base_diameter_m` | 3.658 | SOURCED | Table 2-2: Cable Riser 12 ft base, 32 in tip |
| `structures.230kV_tubular_steel_pole_PSB_local.span_m` | 274.32 | SOURCED | p. 2-16: 'span segments ranging from 250 feet to 1,300 feet' |
| `structures.230kV_tubular_steel_pole_PSB_local.foundation_max_depth_m` | 18.288 | SOURCED | p. 2-16: max foundation depth ~60 ft, max diameter ~12 ft |
| `structures.230kV_tubular_steel_pole_PSB_local.foundation_max_diameter_m` | 3.658 | SOURCED | p. 2-16 |
| `structures.230kV_tubular_steel_pole_PSB_local.foundation_reveal_above_grade_m` | 0.762 | SOURCED | p. 2-16: 'foundations may add an additional two to three feet above ground level' |
| `structures.230kV_tubular_steel_pole_PSB_local.san_jose_height_limit_m` | 45.72 | SOURCED | footnote 7: within San Jose, transmission structure heights limited to 150 ft in nonresidential/non-urban designations |
| `structures.230kV_tubular_steel_pole_PSB_local.line_rating_MVA` | 1000 | SOURCED | Sec 2.6: 'rated at approximately 1,000 megavolt-amperes' |
| `structures.230kV_tubular_steel_pole_PSB_local.shield_wires_count` | 2 | SOURCED | Sec 2.6.1.1: 'two overhead optical ground wires' |
| `structures.230kV_tubular_steel_pole_PSB_local.arm_length_pole_cl_to_attachment_m` | 3 | ASSUMED | ASSUMED: Not dimensioned in Fig. 2-4. Derived floor: GO95 conductor-to-structure 0.775 m + horizontal swing of a 2.56 m string at 35 deg (1.47 m) + pole radius at arm height ~0.5 m = 2.75 m; rounded up to 3.0 m. Swing angle 35 deg is an engineering assumption. |
| `structures.230kV_tubular_steel_pole_PSB_local.delta_vertical_phase_spacing_m` | 6 | ASSUMED | ASSUMED: Not dimensioned. Floor = GO95 vertical separation at 230 kV (3.10 m) + suspension string length (2.56 m, JM Fig 2-8) = 5.66 m; rounded to 6.0 m. |
| `structures.230kV_lattice_tower_PGE.height_m` | 37.338 | SOURCED | Table 2-5: 'Structure heights: approximately 95 feet to 150 feet'; Figs 2-7/2-8 '95-150 feet' |
| `structures.230kV_lattice_tower_PGE.height_range_alt_m` | [24.384, 45.72] | SOURCED | Table 1: lattice towers and TSPs 'Structure heights: 80 feet to 150 feet' |
| `structures.230kV_lattice_tower_PGE.span_m` | 335.28 | SOURCED | Table 2-5: 'Approximate distance between structures: 700 to 1,500 feet' |
| `structures.230kV_lattice_tower_PGE.span_range_alt_m` | [243.84, 609.6] | SOURCED | Table 1: 800 to 2,000 feet |
| `structures.230kV_lattice_tower_PGE.design_min_ground_clearance_m` | 9.754 | SOURCED | Table 1: 'Minimum ground clearance: 32 feet' (PG&E design, > GO95 30 ft) |
| `structures.230kV_lattice_tower_PGE.row_width_double_circuit_m` | 33.528 | SOURCED | 'An easement of between 100 to 120 feet wide is required for 230 kV double-circuit' |
| `structures.230kV_lattice_tower_PGE.configuration` | double-circuit, three crossarms (vertical phase stack each side), single OPGW at peak | SOURCED | Fig 2-8 in-line view (230 kV one side, 60 kV other side), OPGW on peak |
| `structures.230kV_lattice_tower_PGE.crossarm_half_width_m` | 4 | ASSUMED | ASSUMED: Not dimensioned (figure 'Not to Scale'). Floor = GO95 230 kV conductor-to-steel 0.775 m + string swing 1.47 m (35 deg) + half tower-body width at arm level ~1.5 m = 3.75 m, rounded to 4.0 m. |
| `structures.230kV_lattice_tower_PGE.arm_vertical_spacing_m` | 6 | ASSUMED | ASSUMED: Same derivation as 230 kV TSP: GO95 vertical 3.10 m + string 2.56 m = 5.66 m -> 6.0 m. |
| `structures.230kV_lattice_tower_PGE.base_square_side_m` | 8 | ASSUMED | ASSUMED: No sourced footprint. Typical 230 kV double-circuit lattice base width ~ height/5 for a 37 m tower (~7.5 m); rounded to 8 m. Mark as illustrative. |
| `structures.230kV_lattice_tower_PGE.peak_height_above_top_arm_m` | 3 | ASSUMED | ASSUMED: OPGW shield angle geometry not sourced; 3 m gives roughly 30 deg shielding over the outer top phase for a 4 m half-arm. Illustrative. |
| `structures.230kV_tubular_steel_pole_double_circuit_PGE.height_m` | 33.528 | SOURCED | Fig 2-9 'Typical Tangent Tubular Steel Pole' labelled '100-120 feet' |
| `structures.230kV_tubular_steel_pole_double_circuit_PGE.configuration` | three davit-style crossarms each side (230 kV one side, 60 kV other in JM), OPGW on top | SOURCED | Sec 2.5 Construction, Tubular Steel Poles paragraph: 'double-circuit tubular steel pole structures will also have three cross arms, each supporting a phase conductor on each side' |
| `structures.230kV_wood_pole_existing_PGE.height_m` | 27.432 | SOURCED | Metcalf-Monta Vista 230 kV: replacement TSPs 'approximately ten feet higher than the existing wood poles, for a total height of approximately 100 feet' -> existing ~90 ft |
| `structures.230kV_wood_pole_existing_PGE.replacement_tsp_height_m` | 30.48 | SOURCED | same sentence |
| `structures.115kV_tubular_steel_pole_Nortech_local.single_circuit_height_m` | 22.86 | SOURCED | Kifer-Nortech 115 kV: light-duty steel and self-supporting TSPs 60 to 90 feet tall |
| `structures.115kV_tubular_steel_pole_Nortech_local.double_circuit_height_m` | 26.67 | SOURCED | Trimble-Nortech 115 kV double-circuit self-supporting TSPs 80 to 95 feet tall |
| `structures.115kV_tubular_steel_pole_Nortech_local.span_light_duty_m` | 114.3 | SOURCED | spans ~300-450 ft (light-duty) |
| `structures.115kV_tubular_steel_pole_Nortech_local.span_self_supporting_m` | 167.64 | SOURCED | spans ~500-600 ft (self-supporting, Kifer-Nortech) |
| `structures.115kV_tubular_steel_pole_Nortech_local.span_double_circuit_m` | 205.74 | SOURCED | Trimble-Nortech spans 550-800 ft |
| `structures.115kV_tubular_steel_pole_Nortech_local.tsp_foundation_diameter_m` | 1.524 | SOURCED | self-supporting foundations ~5 ft diameter, 16 ft deep |
| `structures.115kV_tubular_steel_pole_Nortech_local.tsp_foundation_depth_m` | 4.877 | SOURCED | same |
| `structures.115kV_tubular_steel_pole_Nortech_local.lds_foundation_diameter_m` | 0.914 | SOURCED | light-duty ~3 ft diameter, 9-12 ft deep |
| `structures.115kV_tubular_steel_pole_Nortech_local.arm_length_pole_cl_to_attachment_m` | 2 | ASSUMED | ASSUMED: Not sourced. Floor: GO95 115 kV conductor-to-structure 0.483 m + swing of 1.46 m string at 35 deg (0.84 m) + pole radius ~0.4 m = 1.72 m -> 2.0 m. |
| `structures.115kV_tubular_steel_pole_Nortech_local.arm_vertical_spacing_m` | 3.5 | ASSUMED | ASSUMED: Floor: GO95 115 kV vertical 1.93 m + string 1.46 m = 3.39 m -> 3.5 m. |
| `structures.115kV_lattice_tower_PGE.height_m` | 24.994 | SOURCED | Moss Landing-Salinas-Soledad 115 kV double-circuit LSTs: 'Structure heights: Similar to existing; averaging 82 feet above ground surface' |
| `structures.115kV_lattice_tower_PGE.span_m` | 259.08 | SOURCED | 'Span lengths: Between 51 feet to 1,847 feet, averaging approximately 850 feet' |
| `structures.115kV_lattice_tower_PGE.design_min_ground_clearance_m` | 9.144 | SOURCED | 'The minimum ground to conductor clearance would be 30 feet' |
| `structures.115kV_lattice_tower_PGE.footings` | four drilled-pier concrete footings, ~3 ft above ground | SOURCED | Summary of Project Components |
| `structures.115kV_lattice_tower_PGE.footing_reveal_m` | 0.914 | SOURCED | 'typical footing would be approximately three feet aboveground' |
| `structures.115kV_lattice_tower_PGE.crossarm_half_width_m` | 2.6 | ASSUMED | ASSUMED: Not sourced. Floor: GO95 0.483 m + swing 0.84 m + half body ~1.0 m = 2.32 m -> 2.6 m. |
| `structures.115kV_lattice_tower_PGE.note` | Central Coast PG&E line (not Alviso); used because no North San Jose 115 kV lattice dimensions were found. | SOURCED | n/a |
| `structures.115kV_steel_pole_PGE_alt.height_m` | 25.146 | SOURCED | TSP/LDS 'approximately 70 to 95 feet in height' |
| `structures.115kV_steel_pole_PGE_alt.base_diameter_m` | 1.372 | SOURCED | 'approximately two to seven feet in diameter at the base' |
| `structures.115kV_steel_pole_PGE_alt.span_m` | 89.916 | SOURCED | spans 94-935 ft, average ~295 ft |
| `structures.115kV_steel_pole_PGE_alt.existing_wood_pole_height_range_m` | [18.288, 27.432] | SOURCED | Table 2-2 single-circuit wood poles 60 to 90 feet |
| `structures.60kV_PGE.on_shared_230kV_structures` | PG&E 60 kV circuit carried on the same lattice/TSP as 230 kV, insulated at 115 kV | SOURCED | Sec 2.3.2.2: 'The eastern-most circuit will remain energized at 60 kV and will utilize 115 kV insulators and support hardware' |
| `structures.60kV_PGE.design_min_ground_clearance_m` | 9.144 | SOURCED | Table 2-5 60 kV: 'Minimum ground clearance: 30 feet' |
| `structures.60kV_PGE.wood_pole_height_m` | 18.288 | ASSUMED | ASSUMED: No sourced 60 kV wood-pole height for SVP/PG&E North San Jose (SVP documents returned HTTP 403). 60 ft is a placeholder at the low end of the PG&E wood-pole range quoted for 115 kV (60-90 ft, Hollister). Do not draw as sourced. |
| `structures.60kV_PGE.span_m` | 76.2 | ASSUMED | ASSUMED: No source; typical urban sub-transmission wood-pole span, below Hollister pole-line average (295 ft at 115 kV). |
| `structures.ruling_span_assumptions.230kV_ruling_span_m` | 274.32 | ASSUMED | ASSUMED: No ruling span published in the CEQA filings; 900 ft lies inside PSB (250-1300 ft) and JM (700-1500 ft) span ranges. Needed only for sag/DLR illustration. |
| `structures.ruling_span_assumptions.115kV_ruling_span_m` | 182.88 | ASSUMED | ASSUMED: Inside Nortech TSP spans (500-800 ft). |
| `structures.500kV` | None | ASSUMED | ASSUMED: Not drawn. No 500 kV line/substation within the 25 km study radius in OSM data; no 500 kV structure dimensions were researched to sourced standard. |
| `conductors.ACSR_Drake_795_26_7.outer_diameter_mm` | 28.14 | SOURCED | Drake row: complete conductor diameter 1.108 in |
| `conductors.ACSR_Drake_795_26_7.outer_diameter_mm_IEEE738` | 28.14 | SOURCED | Table I: Outer diameter D = 0.02814 m |
| `conductors.ACSR_Drake_795_26_7.aluminum_area_mm2` | 403 | SOURCED | Al area 0.6247 in2 (total 0.7264 in2) |
| `conductors.ACSR_Drake_795_26_7.total_area_mm2` | 468.6 | SOURCED | Total area 0.7264 in2 |
| `conductors.ACSR_Drake_795_26_7.stranding` | 26 Al / 7 St; Al strand 0.1749 in, St strand 0.1360 in, core 0.4080 in | SOURCED | Drake row |
| `conductors.ACSR_Drake_795_26_7.weight_kg_per_m` | 1.6281 | SOURCED | Total weight 1094 lb/1000 ft |
| `conductors.ACSR_Drake_795_26_7.weight_kg_per_m_prysmian` | 1.627 | SOURCED | Masa total 1627 kg/km |
| `conductors.ACSR_Drake_795_26_7.rated_tensile_strength_kN` | 140.1 | SOURCED | Rated breaking strength, standard steel: 31,500 lb (HS 33,500; UHS 35,400) |
| `conductors.ACSR_Drake_795_26_7.rated_tensile_strength_kN_prysmian` | 140.2 | SOURCED | Carga de rotura 14292 kgf |
| `conductors.ACSR_Drake_795_26_7.R_dc_20C_ohm_per_km` | 0.07015 | SOURCED | DC resistance @20C 0.1129 ohm/mile |
| `conductors.ACSR_Drake_795_26_7.R_ac_25C_ohm_per_km` | 0.07283 | SOURCED | Table I: R(25C) = 7.283e-5 ohm/m (IEEE Std 738 Drake example) |
| `conductors.ACSR_Drake_795_26_7.R_ac_75C_ohm_per_km` | 0.08688 | SOURCED | Table I: R(75C) = 8.688e-5 ohm/m |
| `conductors.ACSR_Drake_795_26_7.R_ac_75C_ohm_per_km_prysmian` | 0.0865 | SOURCED | Resistencia AC a 75C 0.0865 ohm/km |
| `conductors.ACSR_Drake_795_26_7.R_ac_200C_ohm_per_km` | 0.122 | SOURCED | Table I: R(200C) = 1.220e-4 ohm/m |
| `conductors.ACSR_Drake_795_26_7.emissivity` | 0.8 | SOURCED | Table I: Emissivity 0.8 (IEEE 738 example value) |
| `conductors.ACSR_Drake_795_26_7.solar_absorptivity` | 0.8 | SOURCED | Table I: Solar absorptivity 0.8 |
| `conductors.ACSR_Drake_795_26_7.max_conductor_temp_C_IEEE738_example` | 100 | SOURCED | Table I: Max temp 100 C |
| `conductors.ACSR_Drake_795_26_7.continuous_operating_temp_C` | 75 | SOURCED | 'Continuous operating temperature - 75C'; emergency 100C |
| `conductors.ACSR_Drake_795_26_7.emergency_operating_temp_C` | 100 | SOURCED | 'Emergency operating temperature - 100C' |
| `conductors.ACSR_Drake_795_26_7.static_ampacity_A` | 907 | SOURCED | Ampacity 907 A at 25C ambient, 75C conductor, wind 0.61 m/s, sun 1033.3 W/m2, emissivity=absorptivity=0.5, sea level |
| `conductors.ACSR_Drake_795_26_7.static_ampacity_conditions` | {"ambient_C": 25, "conductor_C": 75, "wind_m_s": 0.61, "solar_W_m2": 1033.3, "emissivity": 0.5, "absorptivity": 0.5, "elevation_m": 0} | SOURCED | ampacity footnote |
| `conductors.ACSR_Drake_795_26_7.note_emissivity_choice` | Use 0.8/0.8 (IEEE 738 example, conservative for aged conductor in solar gain) for the live DLR solver; 0.5/0.5 only reproduces the Prysmian static table. | ASSUMED | ASSUMED: Choice between two sourced conventions; not itself a sourced fact. |
| `conductors.ACSR_Dove_556p5_26_7.outer_diameter_mm` | 23.55 | SOURCED | Dove row: 0.927 in |
| `conductors.ACSR_Dove_556p5_26_7.aluminum_area_mm2` | 282 | SOURCED | Al 0.4371 in2 |
| `conductors.ACSR_Dove_556p5_26_7.total_area_mm2` | 327.9 | SOURCED | Total 0.5083 in2 |
| `conductors.ACSR_Dove_556p5_26_7.weight_kg_per_m` | 1.1387 | SOURCED | 765.2 lb/1000 ft |
| `conductors.ACSR_Dove_556p5_26_7.rated_tensile_strength_kN` | 100.5 | SOURCED | 22,600 lb (std) |
| `conductors.ACSR_Dove_556p5_26_7.R_dc_20C_ohm_per_km` | 0.10023 | SOURCED | 0.1613 ohm/mile |
| `conductors.ACSR_Dove_556p5_26_7.R_ac_75C_ohm_per_km` | 0.123 | SOURCED | Dove: R_AC 75C 0.123 ohm/km (R_DC20 0.0998) |
| `conductors.ACSR_Dove_556p5_26_7.R_ac_25C_ohm_per_km` | 0.1019 | ASSUMED | ASSUMED: Linear interpolation between sourced R_DC(20C)=0.0998 (Prysmian) and R_AC(75C)=0.123 ohm/km; skin effect at 20C neglected. Check: the same method gives Drake R(25C) = 0.0700+0.0165*5/55 = 0.0715 vs IEEE 738 0.07283 ohm/km, i.e. ~2% low, so expect Dove R(25C) ~2% low as well. |
| `conductors.ACSR_Dove_556p5_26_7.static_ampacity_A` | 726 | SOURCED | Dove ampacity 726 A, same conditions as Drake row |
| `conductors.ACSR_Dove_556p5_26_7.emissivity` | 0.8 | ASSUMED | ASSUMED: Same IEEE 738 default as Drake (no Dove-specific value). |
| `conductors.ACSR_Dove_556p5_26_7.solar_absorptivity` | 0.8 | ASSUMED | ASSUMED: Same IEEE 738 default. |
| `conductors.conductors_used_in_local_Bay_Area_projects.ACSS_954_54_7_diameter_mm` | 30.38 | SOURCED | Table 2-5 230 kV: '954 kcmil ACSS ... Conductor diameter: 1.196 inches' |
| `conductors.conductors_used_in_local_Bay_Area_projects.ACSS_477_24_7_diameter_mm` | 21.49 | SOURCED | Table 2-5 60 kV: 477 kcmil ACSS, 0.846 inches |
| `conductors.conductors_used_in_local_Bay_Area_projects.SSAC_477_115kV_diameter_mm` | 21.49 | SOURCED | 477 kcmil SSAC, 0.846 inch, 115 kV |
| `conductors.conductors_used_in_local_Bay_Area_projects.AAC_1113_230kV_diameter_mm` | 30.99 | SOURCED | Table 1: double-circuit 1113 kcmil AAC, 1.22 inches |
| `conductors.conductors_used_in_local_Bay_Area_projects.OPGW_diameter_mm` | 17.65 | SOURCED | OPGW diameter 0.695 in (approximate) |
| `conductors.conductors_used_in_local_Bay_Area_projects.shield_wire_diameter_mm` | 9.78 | SOURCED | Shield wire diameter 0.385 in |
| `conductors.conductors_used_in_local_Bay_Area_projects.ACCR_715_double_bundle_230kV_rating_MVA` | 310 | SOURCED | Sec 2.2: SJC02 230 kV lines 'will include a 715 double-bundle Aluminum Conductor Composite Reinforced with a current carrying capacity of 310 Mega Volt-Amps' |
| `conductors.conductors_used_in_local_Bay_Area_projects.PSB_underground_cable` | six 2,500 mm2 copper single-core XLPE 230 kV cables (single circuit), duct bank of 12 ducts; splice vaults ~30 x 12 x 10 ft every 1,500-3,000 ft | SOURCED | Sec 2.6.1.2 |
| `insulators.string_length_from_PGE_drawings.230kV_suspension_string_length_m` | 2.56 | SOURCED | Figs 2-8 and 2-9: dimension 8.4' bracketing the dashed 230 kV insulator string |
| `insulators.string_length_from_PGE_drawings.115kV_class_suspension_string_length_m` | 1.463 | SOURCED | Figs 2-8/2-9: 4.8' on the 60 kV circuit, which uses 115 kV insulators and hardware (Ch. 2 text) |
| `insulators.string_length_from_PGE_drawings.60kV_suspension_string_length_m` | 1.463 | ASSUMED | ASSUMED: PG&E JM 60 kV circuit is insulated at 115 kV, so the same 4.8 ft string is used; a pure 60 kV string would be shorter. |
| `insulators.ANSI_52_3_disc.unit_spacing_mm` | 146 | SOURCED | 52-3: Unit Spacing H 146 mm |
| `insulators.ANSI_52_3_disc.shell_diameter_mm` | 254 | SOURCED | 52-3: Shell diameter D 254 mm |
| `insulators.ANSI_52_3_disc.leakage_distance_mm` | 292 | SOURCED | 52-3: leakage 292 mm (Victor VI 52-3H TG lists 12.5 in = 317.5 mm for its high-leakage variant) |
| `insulators.ANSI_52_3_disc.combined_ME_strength_kN` | 70 | SOURCED | 52-3: 70 kN (Victor 52-3H: 20,000 lb = 89 kN) |
| `insulators.disc_count_typical.69kV_discs` | 4 | SOURCED | table row 69 kV: 4 |
| `insulators.disc_count_typical.115kV_discs` | 6 | SOURCED | 115 kV: 6 |
| `insulators.disc_count_typical.138kV_discs` | 8 | SOURCED | 138 kV: 8 |
| `insulators.disc_count_typical.230kV_discs` | 14 | SOURCED | 230 kV: 14 |
| `insulators.disc_count_typical.345kV_discs` | 18 | SOURCED | 345 kV: 18 |
| `insulators.disc_count_typical.500kV_discs` | 34 | SOURCED | 500 kV: 34 |
| `insulators.disc_count_typical.60kV_discs` | 4 | ASSUMED | ASSUMED: Nearest tabulated class is 69 kV (4 discs). |
| `insulators.disc_count_typical.note` | Generic (Diesendorf 1974) counts give 14 x 146 mm = 2.04 m for 230 kV, shorter than the PG&E drawn 2.56 m string (which includes hardware and possibly extra units for coastal/bay contamination). For 3D drawing use the PG&E string lengths; disc count drawn = round((L - 0.30 m hardware)/0.146) = 15 at 230 kV, 8 at 115 kV class. | ASSUMED | ASSUMED: Hardware allowance 0.30 m is assumed. |
| `insulators.polymer_option.corona_ring_required_from_kV` | 220 | SOURCED | p. 3-36: 'The use of an external corona shielding ring is required at 220 / 230 kV and above' |
| `insulators.polymer_option.230kV_line_end_ring_diameter_mm` | 203 | SOURCED | Recommended Corona Ring table: 220/230 kV ground end None, line end 8" (203 mm) |
| `insulators.polymer_option.500kV_line_end_ring_diameter_mm` | 381 | SOURCED | 500 kV: ground end 8" (203 mm), line end 15" (381 mm) |
| `transformers.230_115kV_300MVA_three_phase_DOE.length_m` | 8.23 | SOURCED | Table 2: 230-115 kV, 300 MVA three-phase: 170 tons (340,000 lb), 21ft W x 27ft L x 25ft H |
| `transformers.230_115kV_300MVA_three_phase_DOE.width_m` | 6.401 | SOURCED | same row |
| `transformers.230_115kV_300MVA_three_phase_DOE.height_m` | 7.62 | SOURCED | same row |
| `transformers.230_115kV_300MVA_three_phase_DOE.weight_t` | 154.2 | SOURCED | 170 short tons = 340,000 lb |
| `transformers.230_115kV_300MVA_three_phase_DOE.note` | Table cells in the PDF text layer are offset by one line; pairing of weight/dimensions to the 230-115 kV row was checked against the ordering of the four transmission rows (170/335/410/235 tons). | SOURCED | Table 2 |
| `transformers.230_115kV_420MVA_PGE_bank.rating_MVA` | 420 | SOURCED | Martin Substation: 'the new 230/115 kV, 420 MVA, transformer bank'; Table 2-5 also lists 'three, 134 MVA, 230/115 kV transformers' (single-phase units, 3 x 134 = 402 MVA) |
| `transformers.230_115kV_420MVA_PGE_bank.Los_Esteros_bank_count` | 3 x 230/115 kV banks initially, 4th planned; plus 4 x 230/21 kV banks | SOURCED | Los Esteros Substation description |
| `transformers.230_115kV_420MVA_PGE_bank.length_m` | 8.952 | ASSUMED | ASSUMED: Scaled from DOE 300 MVA unit with linear dimension ~ S^0.25 (mass ~ S^0.75 transformer scaling law). Not a datasheet value. |
| `transformers.230_115kV_420MVA_PGE_bank.width_m` | 6.963 | ASSUMED | ASSUMED: Same scaling. |
| `transformers.230_115kV_420MVA_PGE_bank.height_m` | 8.289 | ASSUMED | ASSUMED: Same scaling (tank+bushings envelope uncertain). |
| `transformers.230_115kV_420MVA_PGE_bank.weight_t` | 198.5 | ASSUMED | ASSUMED: Mass ~ S^0.75 from 154.2 t at 300 MVA. |
| `transformers.115_21kV_45MVA_distribution_bank.rating_MVA` | 45 | SOURCED | 'three 45 MVA 115 kV - 21 kV transformers' at build-out, two installed |
| `transformers.115_21kV_45MVA_distribution_bank.reference_unit` | WEG 2017, 30/40/50/56 MVA ONAN/ONAF, 115 kV delta / 12.47Y kV, Z = 9%, HV BIL 550 kV, LV BIL 110 kV | SOURCED | listing JVT-3879 |
| `transformers.115_21kV_45MVA_distribution_bank.length_m` | 4.0386 | SOURCED | Dimensions 111"W x 140"H x 159"L (listing does not say whether shipping or overall) |
| `transformers.115_21kV_45MVA_distribution_bank.width_m` | 2.8194 | SOURCED | same |
| `transformers.115_21kV_45MVA_distribution_bank.height_m` | 3.556 | SOURCED | same |
| `transformers.115_21kV_45MVA_distribution_bank.total_weight_t` | 49.8 | SOURCED | Total weight 109,807 lb (shipping weight 97,807 lb; oil 24,927 lb / 3,434 gal; listing figures not mutually consistent) |
| `transformers.115_21kV_45MVA_distribution_bank.installed_envelope_note` | The 2.8 x 4.0 m plan is a tank envelope; radiators, conservator and HV bushings typically add 1.5-2.5 m in plan and ~2 m in height. Draw a 4.5 x 6.0 x 5.5 m installed envelope if showing bushings. | ASSUMED | ASSUMED: Engineering assumption, no outline drawing found. |
| `transformers.230_21kV_45MVA_distribution_bank.rating_MVA` | 45 | SOURCED | 'four 230/21 kV, 45 MVA transformers' per station; also Vasona 230/12 kV 45 MVA and Los Esteros/SJC02 one-line '(2) 230/21kV 45MVA XFMR's' |
| `transformers.115_13p8kV_75MVA_GSU_DOE.length_m` | 7.62 | SOURCED | Table 2 GSU 115-13.8 kV 75 MVA: 110 tons (220,000 lb), 16ft W x 25ft L x 20ft H |
| `transformers.115_13p8kV_75MVA_GSU_DOE.width_m` | 4.877 | SOURCED | same |
| `transformers.115_13p8kV_75MVA_GSU_DOE.height_m` | 6.096 | SOURCED | same |
| `transformers.115_13p8kV_75MVA_GSU_DOE.weight_t` | 99.8 | SOURCED | 220,000 lb |
| `transformers.NRS_230_115kV_additions` | two new 230/115 kV transformers in parallel with one existing (ratings not disclosed for security) | SOURCED | Sec 2.6.2.2 |
| `substation_layout.230kV_PGE_Newark.max_structure_height_in_yard_m` | 19.812 | SOURCED | Sec 2.6.2.1: new structures within Newark 230 kV perimeter 'up to approximately 65 feet above grade (... existing structures are also up to 65 feet)' |
| `substation_layout.230kV_PGE_Newark.max_structure_height_outside_perimeter_m` | 48.768 | SOURCED | existing structures outside perimeter on PG&E property up to 160 ft; new up to 150 ft |
| `substation_layout.230kV_SVP_NRS.max_structure_height_m` | 17.374 | SOURCED | Sec 2.6.2.2: 'up to approximately 57 feet above grade (... existing structures are also approximately 57 feet)' |
| `substation_layout.230kV_SVP_NRS.fence` | 8 ft chain-link (N, W); 10 ft concrete post-and-panel (S, E) | SOURCED | Sec 2.6.2.2 |
| `substation_layout.230kV_bay.breaker_bay_centerline_spacing_m` | 19.812 | SOURCED | Sec III: 'Typical breaker bay centerline to adjacent bay breaker centerline distances is 65' for 230kV and 110' for 500kV' |
| `substation_layout.230kV_bay.500kV_breaker_bay_spacing_m` | 33.528 | SOURCED | same sentence |
| `substation_layout.230kV_bay.perimeter_corridor_m` | 6.096 | SOURCED | 'A corridor, typically 15 - 25 feet in width, must be provided around the inside perimeter' |
| `substation_layout.230kV_bay.rigid_bus_phase_spacing_m` | 4.6 | ASSUMED | ASSUMED: RUS Bulletin 1724E-300 (the usual public reference) returned HTTP 403 and was not read. 4.6 m (15 ft) is an assumed 230 kV (900-1050 kV BIL) centerline spacing; verify against IEEE 605 / RUS before treating as fact. |
| `substation_layout.230kV_bay.low_bus_height_m` | 6.1 | ASSUMED | ASSUMED: Assumed 20 ft equipment/low-bus level; must exceed personnel safety clearance. Upper bound of all 230 kV yard steel is the SOURCED 57-65 ft. |
| `substation_layout.230kV_bay.high_bus_or_deadend_height_m` | 17.374 | ASSUMED | ASSUMED: Taken equal to the SOURCED NRS max structure height (dead-end gantries are typically the tallest yard steel). |
| `substation_layout.115kV_bay.breaker_height_m` | 7.62 | SOURCED | Martin 115 kV yard: 'Two new breakers ... would be approximately 25 feet in height' |
| `substation_layout.115kV_bay.bus_conductor` | 4-inch aluminum tubing and bundled 2300 kcmil AL cable | SOURCED | Martin 115 kV bus reconductor |
| `substation_layout.115kV_bay.breaker_bay_centerline_spacing_m` | 12.192 | ASSUMED | ASSUMED: No public 115 kV bay spacing found (PJM gives 230/500 kV only). 40 ft assumed by scaling PJM 230 kV 65 ft roughly with BIL (550 vs 900 kV). |
| `substation_layout.115kV_bay.rigid_bus_phase_spacing_m` | 2.4 | ASSUMED | ASSUMED: Assumed 8 ft centerline for 550 kV BIL; RUS 1724E-300 not reachable (HTTP 403). |
| `substation_layout.115kV_bay.low_bus_height_m` | 4.9 | ASSUMED | ASSUMED: Assumed 16 ft. |
| `substation_layout.dead_end_and_misc_PGE.230kV_transition_deadend_height_m` | 14.326 | SOURCED | Transition Structure: 'post and beam steel, full-tension dead-end ... Structure height: 47 feet' |
| `substation_layout.dead_end_and_misc_PGE.230kV_cable_termination_height_m` | 2.743 | SOURCED | 'Cable terminations ... about 9 feet in height' |
| `substation_layout.dead_end_and_misc_PGE.lightning_arrester_height_m` | 1.829 | SOURCED | 'metal oxide varistor type, one per phase, about 6 feet in height' |
| `substation_layout.dead_end_and_misc_PGE.yard_lighting_structure_height_m` | 7.62 | SOURCED | 'low-intensity wattage mounted on approximately 25' structures' |
| `substation_layout.substation_footprints_local.Nortech_115_21kV_site_acres` | 3.3 | SOURCED | 'The site occupies 3.3 acres' (3 x 45 MVA ultimate, 9 feeders) |
| `substation_layout.substation_footprints_local.Nortech_fence_height_m` | 2.438 | SOURCED | 7 ft chain link + 1 ft barbed-wire outrigger |
| `substation_layout.substation_footprints_local.Nortech_microwave_tower_height_m` | 30.48 | SOURCED | '100-foot-tall steel lattice microwave tower with two microwave dishes' |
| `substation_layout.substation_footprints_local.Nortech_pad_elevation_m_NGVD` | 1.829 | SOURCED | site raised to ~6 ft; operates with floodwater at 9 ft NGVD |
| `substation_layout.substation_footprints_local.Vasona_230_12kV_two_bank_plan_m` | [76.2, 45.72] | SOURCED | 'two-transformer bank, low profile facility occupying an area approximately 250 feet by 150 feet' |
| `substation_layout.substation_footprints_local.TriValley_230_21kV_four_bank_site_acres` | 5 | SOURCED | 'Developed acreage: 5 acres, fenced' for four 230/21 kV 45 MVA banks |
| `substation_layout.substation_footprints_local.TriValley_switchgear_building_plan_m` | [6.401, 10.973] | SOURCED | 'Four 21-foot by 36-foot metal-clad switchgear buildings' |
| `substation_layout.substation_footprints_local.TriValley_ring_road_width_m` | 6.096 | SOURCED | '20-foot wide ring road' |
| `substation_layout.substation_footprints_local.Los_Esteros_site_acres` | 24 | SOURCED | 'would occupy the northern 24 acres of a 54-acre property' |
| `substation_layout.data_center_onsite_230kV_substation_SJC02.scheme` | New 2-bay, 6-breaker 230 kV breaker-and-a-half (BAAH) substation, terminals for two 230 kV lines; 230/13.8 kV transformers; ~1,100 ft of 230 kV line to Los Esteros; Los Esteros adds 2 bays with dead-ends, 4 CBs, 10 disconnects | SOURCED | Figure 2-6 interconnection one-line (text layer) |
| `substation_layout.data_center_onsite_230kV_substation_SJC02.supply_lines` | two 230 kV lines, ~0.2 mi (1,000 ft) each, along west fence adjacent to LECEF, to PG&E Los Esteros | SOURCED | Sec 2.1.5 |
| `substation_layout.data_center_onsite_230kV_substation_SJC02.plan_area_m2` | 6967.73 | ASSUMED | ASSUMED: Plan area not disclosed. Assumed 250 x 300 ft: a 2-bay BAAH at PJM 65 ft bay pitch (130 ft) plus transformer row and 20 ft perimeter corridor; compare Vasona 2-bank 250 x 150 ft. |
| `data_center.Microsoft_SJC02_Alviso_reference.location` | 1657 Alviso-Milpitas Road, San Jose; adjacent (east) of PG&E Los Esteros Substation and LECEF | SOURCED | Sec 2.1; CEC order TN 232773 |
| `data_center.Microsoft_SJC02_Alviso_reference.max_load_MW` | 99 | SOURCED | 'maximum electrical load ... 99 MW, although the estimated load is 92 MW' |
| `data_center.Microsoft_SJC02_Alviso_reference.expected_load_MW` | 92 | SOURCED | same |
| `data_center.Microsoft_SJC02_Alviso_reference.site_area_acres` | 64.5 | SOURCED | 'approximately 64.5-acre project site' |
| `data_center.Microsoft_SJC02_Alviso_reference.building_count` | 2 | SOURCED | two single-story buildings SJC02 (north) and SJC03 (south) |
| `data_center.Microsoft_SJC02_Alviso_reference.north_building_area_m2` | 22455 | SOURCED | SJC02 ~241,705 sq ft |
| `data_center.Microsoft_SJC02_Alviso_reference.south_building_area_m2` | 22043 | SOURCED | SJC03 ~237,268 sq ft |
| `data_center.Microsoft_SJC02_Alviso_reference.total_gross_area_m2` | 44501 | SOURCED | 'approximately 479,000 gross square feet' |
| `data_center.Microsoft_SJC02_Alviso_reference.building_height_m` | 8.23 | SOURCED | Land Use fn 2: 'approximately 27 feet tall, with some mechanical equipment extending to a max height of 31 feet'; elevations: T.O. ROOF 26'-10 1/2" |
| `data_center.Microsoft_SJC02_Alviso_reference.max_height_with_mechanical_m` | 9.449 | SOURCED | same |
| `data_center.Microsoft_SJC02_Alviso_reference.generator_count` | 40 | SOURCED | 40 x 3.0 MW Cummins QSK95 diesel standby + 2 admin (1.25, 0.5 MW) |
| `data_center.Microsoft_SJC02_Alviso_reference.generator_enclosure_LxWxH_m` | [17.221, 3.962, 7.62] | SOURCED | Sec 2.2.1: each 3-MW generator ~13 ft wide, 56.5 ft long, 25 ft tall to top of DPF/SCR |
| `data_center.Microsoft_SJC02_Alviso_reference.generator_stack_height_m` | 9.144 | SOURCED | 'separate exhaust stack approximately 30 feet above grade' |
| `data_center.Microsoft_SJC02_Alviso_reference.ups_battery_minutes` | 10 | SOURCED | 'each bank capable of providing up to 10 minutes of backup at 100 percent load' |
| `data_center.Microsoft_SJC02_Alviso_reference.site_grade_elevation_m_amsl` | [3.962, 5.182] | SOURCED | 'elevation of the project site ranges between 13 and 17 feet above mean sea level' |
| `data_center.Microsoft_SJC02_Alviso_reference.FAA_height_limit_m_amsl` | 64.618 | SOURCED | ALUC/FAA limit 212 ft amsl at the site |
| `data_center.Microsoft_SJC02_Alviso_reference.zoning_height_limit_m` | 30.48 | SOURCED | Alviso Master Plan allows heights up to 100 ft on this site |
| `data_center.Microsoft_SJC02_Alviso_reference.utility_supply` | on-site 230 kV substation, 2 x 230 kV lines to PG&E Los Esteros, 715 kcmil double-bundle ACCR, 310 MVA | SOURCED | Sec 2.2 |
| `data_center.Microsoft_SJC02_Alviso_reference.internal_distribution` | 34.5 kV to 480 V unit substation transformers feeding 480 V critical buses and parallel UPS modules | SOURCED | Sec 2.2 |
| `data_center.other_local_data_center_data_points.237_Industrial_Center_option2` | 436,880 sq ft data center, 49.5 MW, with a PG&E substation, on ~26.5 acres (same 1657 Alviso-Milpitas Rd parcel, earlier option) | SOURCED | Ch. 3 cumulative projects table, item 32 |
| `data_center.other_local_data_center_data_points.Santa_Clara_1231_Comstock` | four-story 122,000 sq ft data center, six 3,000 kW diesel generators | SOURCED | cumulative projects table, item 75 |
| `data_center.other_local_data_center_data_points.San_Jose_area_load_forecast_MW` | {"TPP_2021_22": 2100, "TPP_2024_25_base": 3400, "TPP_2024_25_sensitivity": 4200} | SOURCED | Ch. 4 Alternatives: load forecast increase 'Mostly driven by new data center load projections' |
| `data_center.site_150MW_scaled_ASSUMED.load_MW` | 150 | ASSUMED | ASSUMED: Scenario input from the QSiteProof project question; not a real application or interconnection request. |
| `data_center.site_150MW_scaled_ASSUMED.building_gross_area_m2` | 67425 | ASSUMED | ASSUMED: Linear MW scaling of SJC02 (479,000 gsf per 99 MW max). Hyperscale density varies 2x with rack density; illustrative only. |
| `data_center.site_150MW_scaled_ASSUMED.building_height_m` | 8.23 | ASSUMED | ASSUMED: Same single-story form as SJC02. |
| `data_center.site_150MW_scaled_ASSUMED.building_footprint_two_halls_LxW_m` | [180.0, 125.0] | ASSUMED | ASSUMED: Two halls; 2 x 180 x 125 m = 45,000 m2 ~= 0.67 x scaled gross area if mechanical yards are outside; chosen to fit a ~40 ha parcel. Illustrative. |
| `data_center.site_150MW_scaled_ASSUMED.site_area_acres` | 97.7 | ASSUMED | ASSUMED: Linear scaling of SJC02 site area. |
| `data_center.site_150MW_scaled_ASSUMED.onsite_substation` | 230 kV BAAH, 2 lines, 2-3 x 230/34.5 kV transformers ~ 100 MVA each | ASSUMED | ASSUMED: SJC02 used 230 kV with two supply lines; transformer MVA for 150 MW (N-1 with 2 of 3 units carrying load) is an engineering assumption. |
| `clearances_go95._basis` | Clearances apply at 60 F conductor temperature, no wind (Rule 37 for Table 1, Rule 38 for Table 2). Table 1 columns F = 22.5-300 kV (covers 60, 115, 230 kV), G = 300-550 kV (500 kV). | SOURCED | Rule 37 text; Rule 38 text |
| `clearances_go95._voltage_convention` | nominal phase-to-phase kV used for the 'per kV in excess of' increments | ASSUMED | ASSUMED: GO 95 voltage classes are nominal circuit voltages; interpretation, not quoted |
| `clearances_go95.60kV.ground_rural_vehicle_areas_m` | 9.144 | SOURCED | Table 1 Case 4, col F: 30 Feet |
| `clearances_go95.60kV.ground_urban_thoroughfare_m` | 9.144 | SOURCED | Table 1 Case 3, col F: 30 Feet |
| `clearances_go95.60kV.ground_pedestrian_only_m` | 7.62 | SOURCED | Table 1 Case 5, col F: 25 Feet |
| `clearances_go95.60kV.railroad_freight_crossing_m` | 10.363 | SOURCED | Table 1 Case 1, col F: 34 Feet |
| `clearances_go95.60kV.above_walkable_building_surface_m` | 3.658 | SOURCED | Table 1 Case 6, col F: 12 Feet |
| `clearances_go95.60kV.horizontal_from_buildings_m` | 1.829 | SOURCED | Table 1 Case 7, col F: 6 Feet |
| `clearances_go95.60kV.water_not_sailboating_m` | 7.62 | SOURCED | Table 1 Case 11, col F: 25 Feet |
| `clearances_go95.60kV.conductor_to_pole_centerline_min_m` | 0.4572 | SOURCED | Table 1 Case 8, col F: 18 inches |
| `clearances_go95.60kV.conductor_to_structure_surface_min_m` | 0.3048 | SOURCED | Table 1 Case 9, col F: 1/4 of Table 2 Case 15 pin spacing = 12.0 in at 60 kV |
| `clearances_go95.60kV.radial_to_vegetation_min_m` | 0.3048 | SOURCED | Table 1 Case 13, col F: 1/4 pin spacing (Table 2 Case 15) = 12.0 in |
| `clearances_go95.60kV.phase_to_phase_horizontal_min_m` | 1.2192 | SOURCED | Table 2 Case 15 (pin spacing, same crossarm) at 60 kV = 48.0 in |
| `clearances_go95.60kV.phase_to_phase_vertical_min_m` | 1.2192 | SOURCED | Table 2 Case 12 col H (vertical separation, separate crossarms) = 48.0 in |
| `clearances_go95.60kV.max_reduction_for_temperature_and_loading_cases2to6_frac` | 0.1 | SOURCED | Rule 37: Table 1 Cases 2-6 'shall in no case be reduced more than 10% below the tabular values because of temperature and loading' |
| `clearances_go95.60kV.min_ground_clearance_at_max_sag_rural_m` | 8.23 | SOURCED | 0.9 x Table 1 Case 4 value (Rule 37 10% allowance) |
| `clearances_go95.115kV.ground_rural_vehicle_areas_m` | 9.144 | SOURCED | Table 1 Case 4, col F: 30 Feet |
| `clearances_go95.115kV.ground_urban_thoroughfare_m` | 9.144 | SOURCED | Table 1 Case 3, col F: 30 Feet |
| `clearances_go95.115kV.ground_pedestrian_only_m` | 7.62 | SOURCED | Table 1 Case 5, col F: 25 Feet |
| `clearances_go95.115kV.railroad_freight_crossing_m` | 10.363 | SOURCED | Table 1 Case 1, col F: 34 Feet |
| `clearances_go95.115kV.above_walkable_building_surface_m` | 3.658 | SOURCED | Table 1 Case 6, col F: 12 Feet |
| `clearances_go95.115kV.horizontal_from_buildings_m` | 1.829 | SOURCED | Table 1 Case 7, col F: 6 Feet |
| `clearances_go95.115kV.water_not_sailboating_m` | 7.62 | SOURCED | Table 1 Case 11, col F: 25 Feet |
| `clearances_go95.115kV.conductor_to_pole_centerline_min_m` | 0.4572 | SOURCED | Table 1 Case 8, col F: 18 inches |
| `clearances_go95.115kV.conductor_to_structure_surface_min_m` | 0.4826 | SOURCED | Table 1 Case 9, col F: 1/4 of Table 2 Case 15 pin spacing = 19.0 in at 115 kV |
| `clearances_go95.115kV.radial_to_vegetation_min_m` | 0.4826 | SOURCED | Table 1 Case 13, col F: 1/4 pin spacing (Table 2 Case 15) = 19.0 in |
| `clearances_go95.115kV.phase_to_phase_horizontal_min_m` | 1.9304 | SOURCED | Table 2 Case 15 (pin spacing, same crossarm) at 115 kV = 76.0 in |
| `clearances_go95.115kV.phase_to_phase_vertical_min_m` | 1.9304 | SOURCED | Table 2 Case 13 (vertical separation, separate crossarms) = 76.0 in |
| `clearances_go95.115kV.max_reduction_for_temperature_and_loading_cases2to6_frac` | 0.1 | SOURCED | Rule 37: Table 1 Cases 2-6 'shall in no case be reduced more than 10% below the tabular values because of temperature and loading' |
| `clearances_go95.115kV.min_ground_clearance_at_max_sag_rural_m` | 8.23 | SOURCED | 0.9 x Table 1 Case 4 value (Rule 37 10% allowance) |
| `clearances_go95.230kV.ground_rural_vehicle_areas_m` | 9.144 | SOURCED | Table 1 Case 4, col F: 30 Feet |
| `clearances_go95.230kV.ground_urban_thoroughfare_m` | 9.144 | SOURCED | Table 1 Case 3, col F: 30 Feet |
| `clearances_go95.230kV.ground_pedestrian_only_m` | 7.62 | SOURCED | Table 1 Case 5, col F: 25 Feet |
| `clearances_go95.230kV.railroad_freight_crossing_m` | 10.363 | SOURCED | Table 1 Case 1, col F: 34 Feet |
| `clearances_go95.230kV.above_walkable_building_surface_m` | 3.658 | SOURCED | Table 1 Case 6, col F: 12 Feet |
| `clearances_go95.230kV.horizontal_from_buildings_m` | 1.829 | SOURCED | Table 1 Case 7, col F: 6 Feet |
| `clearances_go95.230kV.water_not_sailboating_m` | 7.62 | SOURCED | Table 1 Case 11, col F: 25 Feet |
| `clearances_go95.230kV.conductor_to_pole_centerline_min_m` | 0.4572 | SOURCED | Table 1 Case 8, col F: 18 inches |
| `clearances_go95.230kV.conductor_to_structure_surface_min_m` | 0.7747 | SOURCED | Table 1 Case 9, col F: 1/4 of Table 2 Case 15 pin spacing = 30.5 in at 230 kV |
| `clearances_go95.230kV.radial_to_vegetation_min_m` | 0.7747 | SOURCED | Table 1 Case 13, col F: 1/4 pin spacing (Table 2 Case 15) = 30.5 in |
| `clearances_go95.230kV.phase_to_phase_horizontal_min_m` | 3.0988 | SOURCED | Table 2 Case 15 (pin spacing, same crossarm) at 230 kV = 122.0 in |
| `clearances_go95.230kV.phase_to_phase_vertical_min_m` | 3.0988 | SOURCED | Table 2 Case 13 (vertical separation, separate crossarms) = 122.0 in |
| `clearances_go95.230kV.max_reduction_for_temperature_and_loading_cases2to6_frac` | 0.1 | SOURCED | Rule 37: Table 1 Cases 2-6 'shall in no case be reduced more than 10% below the tabular values because of temperature and loading' |
| `clearances_go95.230kV.min_ground_clearance_at_max_sag_rural_m` | 8.23 | SOURCED | 0.9 x Table 1 Case 4 value (Rule 37 10% allowance) |
| `clearances_go95.500kV.ground_rural_vehicle_areas_m` | 10.668 | SOURCED | Table 1 Case 4, col G: 30 Feet (kk) + 0.025 ft/kV over 300 kV = 35.0 ft |
| `clearances_go95.500kV.ground_urban_thoroughfare_m` | 10.668 | SOURCED | Table 1 Case 3, col G: 30 Feet (kk) -> 35.0 ft |
| `clearances_go95.500kV.ground_pedestrian_only_m` | 9.144 | SOURCED | Table 1 Case 5, col G: 25 Feet (kk) -> 30.0 ft |
| `clearances_go95.500kV.above_walkable_building_surface_m` | 8.534 | SOURCED | Table 1 Case 6, col G: 20 Feet (ll: +0.04 ft/kV over 300 kV) |
| `clearances_go95.500kV.horizontal_from_buildings_m` | 4.572 | SOURCED | Table 1 Case 7, col G: 15 Feet |
| `clearances_go95.500kV.conductor_to_structure_surface_min_m` | 2.921 | SOURCED | Table 1 Case 9, col G: 1/2 pin spacing = 115.0 in |
| `clearances_go95.500kV.phase_to_phase_horizontal_min_m` | 5.842 | SOURCED | Table 2 Case 15 (pin spacing, same crossarm) at 500 kV = 230.0 in |
| `clearances_go95.500kV.phase_to_phase_vertical_min_m` | 5.842 | SOURCED | Table 2 Case 13 (vertical separation, separate crossarms) = 230.0 in |
| `clearances_go95.500kV.max_reduction_for_temperature_and_loading_cases2to6_frac` | 0.1 | SOURCED | Rule 37: Table 1 Cases 2-6 'shall in no case be reduced more than 10% below the tabular values because of temperature and loading' |
| `clearances_go95.500kV.min_ground_clearance_at_max_sag_rural_m` | 9.601 | SOURCED | 0.9 x Table 1 Case 4 value (Rule 37 10% allowance) |
| `clearances_go95.note_500kV` | No 500 kV substation within 25 km of the site (per substation_ratings.json / OSM); 500 kV values given for completeness only, no 500 kV structure is drawn. | SOURCED | n/a |
