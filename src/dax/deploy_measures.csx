// =============================================================================
//  FLIGHT OPERATIONS INTELLIGENCE 2015 — MEASURE DEPLOYMENT
//  Tabular Editor 2 (free) C# script — creates all 58 measures in one run.
// -----------------------------------------------------------------------------
//  WHY THIS EXISTS
//  Pasting 58 measures into Power BI's formula bar one at a time, then setting
//  58 format strings and 58 display folders by hand, is about 40 minutes of
//  clicking and roughly 58 chances to introduce a typo you will not notice
//  until a number is wrong in a meeting. This does it in four seconds and is
//  re-runnable.
//
//  HOW TO USE
//    1. Install Tabular Editor 2 (free): https://github.com/TabularEditor/TabularEditor/releases
//       Download TabularEditor.Installer.msi, install, close it.
//    2. Open your PBIX in Power BI Desktop.
//    3. Power BI  >  External Tools ribbon  >  Tabular Editor
//       (if the tab is missing, restart Power BI after installing)
//    4. In Tabular Editor:  File > Preferences > check
//       "Allow unsupported Power BI features (experimental)"
//    5. Go to the  C# Script  tab, paste this entire file, press F5.
//    6. Back in Tabular Editor:  File > Save  (Ctrl+S)
//    7. Return to Power BI. The measures are there.
//
//  SAFE TO RE-RUN. Existing measures with the same name are updated in place,
//  not duplicated. Change a measure here, press F5, save — done.
//
//  PREREQUISITE: a table named  _Measures  must already exist.
//  Create it in Power BI first:  Home > Enter data > name it _Measures > Load,
//  then delete Column1. The script will tell you if it is missing.
// =============================================================================

var tableName = "#Measures";   // the table that already exists in this model

if (!Model.Tables.Contains(tableName))
{
    Error("Table '" + tableName + "' not found.\n\n"
        + "Create it in Power BI first:\n"
        + "  Home > Enter data > table name: _Measures > Load\n"
        + "  then right-click Column1 > Delete.\n\n"
        + "Then run this script again.");
    return;
}

var t = Model.Tables[tableName];
int created = 0, updated = 0;

// Upsert helper — the whole point of re-runnability lives here.
Action<string, string, string, string, string> M = (name, expr, folder, format, desc) =>
{
    Measure m;
    if (t.Measures.Contains(name)) { m = t.Measures[name]; updated++; }
    else                           { m = t.AddMeasure(name);  created++; }

    m.Expression    = expr;
    m.DisplayFolder = folder;
    m.Description   = desc;
    if (!string.IsNullOrEmpty(format)) m.FormatString = format;
};


// =============================================================================
//  00 Parameters
// =============================================================================

M("Target OTP", "0.80", "00 Parameters", "0.0%",
  "On-time target. US industry benchmark is 80%. Upgrade path: replace with a "
+ "what-if parameter so the business can move it on the page.");

M("Min Flights For Ranking", "5000", "00 Parameters", "#,0",
  "Volume floor for Best/Worst rankings. Hawaiian flies 3,368 flights against "
+ "Delta's 352,114 - ranking them on one axis without a floor produces "
+ "statistically meaningless winners.");


// =============================================================================
//  01 Base Counts
// =============================================================================

M("Total Flights", "COUNTROWS( flights )", "01 Base Counts", "#,0",
  "Baseline 1,949,742");

M("On Time Flights",
  "CALCULATE( [Total Flights], flights[Flight Status] = \"On Time\" )",
  "01 Base Counts", "#,0", "Baseline 1,525,904");

M("Delayed Flights",
  "CALCULATE( [Total Flights], flights[Flight Status] = \"Delayed\" )",
  "01 Base Counts", "#,0", "Baseline 390,262. Arrival delay >= 15 min, per US DOT.");

M("Cancelled Flights",
  "CALCULATE( [Total Flights], flights[Flight Status] = \"Cancelled\" )",
  "01 Base Counts", "#,0", "Baseline 28,570");

M("Diverted Flights",
  "CALCULATE( [Total Flights], flights[Flight Status] = \"Diverted\" )",
  "01 Base Counts", "#,0", "Baseline 5,006");

M("Completed Flights",
  "[Total Flights] - [Cancelled Flights] - [Diverted Flights]",
  "01 Base Counts", "#,0",
  "Baseline 1,916,166. Cancelled and diverted rows carry a NULL ARRIVAL_DELAY - "
+ "verified, the N/A delay band holds exactly 28,570 + 5,006 rows. They have no "
+ "punctuality outcome, so they cannot sit in a punctuality denominator.");


// =============================================================================
//  02 Rate KPIs  -  two on-time rates, two names, no measure called "On Time %"
// =============================================================================

M("On Time % (Completed)",
  "DIVIDE( [On Time Flights], [Completed Flights] )",
  "02 Rate KPIs", "0.0%",
  "OPERATIONAL KPI. Baseline 79.6%. Denominator = flights that actually "
+ "operated. Answers: of the flights we operated, how many landed on time? "
+ "Use for trending, hub comparison, the report headline.");

M("On Time % (Scheduled)",
  "DIVIDE( [On Time Flights], [Total Flights] )",
  "02 Rate KPIs", "0.0%",
  "CUSTOMER KPI. Baseline 78.3%. Denominator = the whole published schedule. "
+ "Use for carrier league tables: without it an airline can raise its score by "
+ "cancelling its weakest flights. American Eagle cancels 4.84% of its schedule "
+ "against Delta's 0.35%; on the Completed basis that difference is invisible.");

M("Delay Rate %",
  "DIVIDE( [Delayed Flights], [Completed Flights] )",
  "02 Rate KPIs", "0.0%",
  "Baseline 20.4%. INVARIANT: On Time % (Completed) + Delay Rate % = 100.0%.");

M("Cancellation Rate %",
  "DIVIDE( [Cancelled Flights], [Total Flights] )",
  "02 Rate KPIs", "0.00%",
  "Baseline 1.47%. Denominator is TOTAL on purpose: a cancellation is a broken "
+ "promise, measured against what was promised. A delay is a property of a "
+ "flight that operated. Mixing the two is the most common error in aviation "
+ "reporting.");

M("Diverted Rate %",
  "DIVIDE( [Diverted Flights], [Total Flights] )",
  "02 Rate KPIs", "0.00%", "Baseline 0.26%");

M("Disruption Rate %",
  "DIVIDE( [Delayed Flights] + [Cancelled Flights] + [Diverted Flights], [Total Flights] )",
  "02 Rate KPIs", "0.0%",
  "Baseline 21.7% (423,838 / 1,949,742 = 21.74%). The single number for an "
+ "executive: what share of the published schedule did not go to plan.");


// =============================================================================
//  03 Delay Magnitude
// =============================================================================

M("Avg Arrival Delay", "AVERAGE( flights[ARRIVAL_DELAY] )",
  "03 Delay Magnitude", "0.0 \"min\"",
  "Baseline 5.8 min. Strongly right-skewed. Never show without the median.");

M("Median Arrival Delay", "MEDIAN( flights[ARRIVAL_DELAY] )",
  "03 Delay Magnitude", "0.0 \"min\"",
  "Baseline -4 min. The gap between -4 and +5.8 is the story: most flights "
+ "arrive early, a small tail of severe delays drags the mean positive. "
+ "PERFORMANCE: the most expensive measure here. Card only - never in a matrix "
+ "broken down by airline x month x airport.");

M("Avg Delay (Delayed Only)",
  "CALCULATE( AVERAGE( flights[ARRIVAL_DELAY] ), flights[Flight Status] = \"Delayed\" )",
  "03 Delay Magnitude", "0.0 \"min\"",
  "The honest answer to: when we are late, how late are we?");

M("Total Positive Delay Minutes",
  "CALCULATE( SUM( flights[ARRIVAL_DELAY] ), flights[ARRIVAL_DELAY] > 0 )",
  "03 Delay Magnitude", "#,0",
  "NOT comparable to Total Attributed Delay Min: this counts every minute of "
+ "positive delay including flights 1-14 min late, which carry no attribution. "
+ "The two will never reconcile, which is why they carry different names. "
+ "The > 0 filter matters: a plain SUM lets early arrivals net off real delays, "
+ "and an aircraft landing 20 min early does not refund another's 20-min delay.");

M("Max Arrival Delay", "MAX( flights[ARRIVAL_DELAY] )",
  "03 Delay Magnitude", "#,0", "Baseline 1,593 min (26.5 hours)");

M("Avg Departure Delay", "AVERAGE( flights[DEPARTURE_DELAY] )",
  "03 Delay Magnitude", "0.0 \"min\"", "Baseline 10.9 min");

M("Avg Delay Recovery", "AVERAGE( flights[Delay Recovery] )",
  "03 Delay Magnitude", "0.0 \"min\"",
  "Positive = minutes made up in the air. Measures schedule padding plus how "
+ "hard the airline flies to claw back a late departure. Do NOT derive this by "
+ "subtracting Avg Departure Delay - Avg Arrival Delay: those two means cover "
+ "different row populations and the subtraction is invalid.");

M("Recovery Rate %",
  "VAR Recovered = CALCULATE( [Total Flights], flights[Delay Recovery] > 0 )\n"
+ "RETURN DIVIDE( Recovered, [Completed Flights] )",
  "03 Delay Magnitude", "0.0%",
  "Share of operated flights that arrived relatively earlier than they departed.");


// =============================================================================
//  04 Delay Attribution
//  These five columns are populated only when arrival delay >= 15 min (390,262
//  rows, 79.98% NULL). The NULLs are structural and deliberately preserved, so
//  AVERAGE divides by 390,262 automatically with no CALCULATE filter needed.
// =============================================================================

M("Air System Delay Min", "SUM( flights[AIR_SYSTEM_DELAY] )",
  "04 Delay Attribution", "#,0", "4,696,308 min | 21.1% of attributed");

M("Security Delay Min", "SUM( flights[SECURITY_DELAY] )",
  "04 Delay Attribution", "#,0", "25,717 min | 0.1% of attributed");

M("Airline Delay Min", "SUM( flights[AIRLINE_DELAY] )",
  "04 Delay Attribution", "#,0", "7,542,717 min | 33.8% of attributed");

M("Late Aircraft Delay Min", "SUM( flights[LATE_AIRCRAFT_DELAY] )",
  "04 Delay Attribution", "#,0",
  "8,709,198 min | 39.1% of attributed - the single largest cause");

M("Weather Delay Min", "SUM( flights[WEATHER_DELAY] )",
  "04 Delay Attribution", "#,0", "1,328,155 min | 6.0% of attributed");

M("Total Attributed Delay Min",
  "[Air System Delay Min] + [Security Delay Min] + [Airline Delay Min]\n"
+ "    + [Late Aircraft Delay Min] + [Weather Delay Min]",
  "04 Delay Attribution", "#,0", "Baseline 22,302,095 min");

M("Controllable Delay %",
  "DIVIDE( [Airline Delay Min] + [Late Aircraft Delay Min], [Total Attributed Delay Min] )",
  "04 Delay Attribution", "0.0%",
  "THE HEADLINE FINDING. Baseline 72.9% (16,251,915 / 22,302,095). Airline "
+ "delay is the carrier's own fault directly; late-aircraft delay is that same "
+ "fault propagating from a previous leg. At 72.9%, delay here is a scheduling "
+ "and turnaround problem, not weather. That reframes the whole remediation "
+ "conversation: buffer time and turnaround discipline, not meteorology.");

M("Avg Attributed Delay per Delayed Flight",
  "DIVIDE( [Total Attributed Delay Min], [Delayed Flights] )",
  "04 Delay Attribution", "0.0 \"min\"",
  "Baseline 57.1 min. Gives the attribution folder a per-flight scale an "
+ "executive can hold in their head.");

M("Avg Air System Delay",    "AVERAGE( flights[AIR_SYSTEM_DELAY] )",     "04 Delay Attribution", "0.0 \"min\"", "");
M("Avg Security Delay",      "AVERAGE( flights[SECURITY_DELAY] )",       "04 Delay Attribution", "0.0 \"min\"", "");
M("Avg Airline Delay",       "AVERAGE( flights[AIRLINE_DELAY] )",        "04 Delay Attribution", "0.0 \"min\"", "");
M("Avg Late Aircraft Delay", "AVERAGE( flights[LATE_AIRCRAFT_DELAY] )",  "04 Delay Attribution", "0.0 \"min\"", "");
M("Avg Weather Delay",       "AVERAGE( flights[WEATHER_DELAY] )",        "04 Delay Attribution", "0.0 \"min\"", "");


// =============================================================================
//  05 Cancellation Analysis
// =============================================================================

M("Weather Cancellations",
  "CALCULATE( [Cancelled Flights], cancellation_codes[CANCELLATION_REASON] = \"B\" )",
  "05 Cancellation Analysis", "#,0", "Baseline 16,372");

M("Carrier Cancellations",
  "CALCULATE( [Cancelled Flights], cancellation_codes[CANCELLATION_REASON] = \"A\" )",
  "05 Cancellation Analysis", "#,0", "Baseline 8,084");

M("Air System Cancellations",
  "CALCULATE( [Cancelled Flights], cancellation_codes[CANCELLATION_REASON] = \"C\" )",
  "05 Cancellation Analysis", "#,0", "Baseline 4,112");

M("Security Cancellations",
  "CALCULATE( [Cancelled Flights], cancellation_codes[CANCELLATION_REASON] = \"D\" )",
  "05 Cancellation Analysis", "#,0",
  "Baseline 2. Too small to visualise; exists so the four codes reconcile to "
+ "28,570 on the validation page.");

M("Weather Cancellation %",
  "DIVIDE( [Weather Cancellations], [Cancelled Flights] )",
  "05 Cancellation Analysis", "0.0%",
  "Baseline 57.3% (16,372 / 28,570). PUT THIS NEXT TO Controllable Delay % ON "
+ "ONE PAGE. Weather causes 6.0% of delay MINUTES but 57.3% of CANCELLATIONS. "
+ "Airlines absorb bad weather by delaying; when a delay can no longer absorb "
+ "it, they cancel. Two levers, two narratives, one slide.");

M("Cancellations per 1000 Flights",
  "DIVIDE( [Cancelled Flights], [Total Flights] ) * 1000",
  "05 Cancellation Analysis", "0.0",
  "Baseline 14.7 per 1,000. Easier to hold than \"1.47%\".");


// =============================================================================
//  06 Time Intelligence
//  October 2015 contains zero rows. Guard every time-series visual with
//  [Is Comparable Period] = 1 or 'Date Table'[Has Flight Data].
// =============================================================================

M("Flights PM",
  "CALCULATE( [Total Flights], DATEADD( 'Date Table'[Date], -1, MONTH ) )",
  "06 Time Intelligence", "#,0", "Previous month");

M("Flights MoM %",
  "VAR Curr = [Total Flights]\n"
+ "VAR Prev = [Flights PM]\n"
+ "RETURN IF( NOT ISBLANK( Prev ) && NOT ISBLANK( Curr ), DIVIDE( Curr - Prev, Prev ) )",
  "06 Time Intelligence", "0.0%",
  "Guard BOTH sides. Guarding only the prior period still publishes a "
+ "real-looking -100.0% for October, where Curr is blank and Prev is "
+ "September's 172,409.");

M("On Time % PM",
  "CALCULATE( [On Time % (Completed)], DATEADD( 'Date Table'[Date], -1, MONTH ) )",
  "06 Time Intelligence", "0.0%", "");

M("On Time % MoM (pp)",
  "VAR Curr = [On Time % (Completed)]\n"
+ "VAR Prev = [On Time % PM]\n"
+ "RETURN IF( NOT ISBLANK( Prev ) && NOT ISBLANK( Curr ), Curr - Prev )",
  "06 Time Intelligence", "0.0%",
  "The name carries (pp) because this is a difference in PERCENTAGE POINTS, not "
+ "a percentage change. Labelling a 3.0pp move as +3% is a classic error.");

M("Rolling 3M On Time %",
  "CALCULATE( [On Time % (Completed)],\n"
+ "    DATESINPERIOD( 'Date Table'[Date], MAX( 'Date Table'[Date] ), -3, MONTH ) )",
  "06 Time Intelligence", "0.0%",
  "Must be CALCULATE, not AVERAGEX. DATESINPERIOD returns a table of individual "
+ "DATES, so AVERAGEX would iterate ~90 days and return the UNWEIGHTED mean of "
+ "90 daily rates - a quiet Tuesday with 4,000 flights counting the same as a "
+ "Friday with 7,000. CALCULATE recomputes the ratio over the whole window, so "
+ "it is correctly volume-weighted.");

M("Is Comparable Period",
  "IF( [Total Flights] > 0 && [Flights PM] > 0, 1, 0 )",
  "06 Time Intelligence", "0",
  "Drop into the Filters pane (= 1) on every MoM visual so the October gap "
+ "never reaches a stakeholder's eye as a real business event.");


// =============================================================================
//  07 Ranking & Dynamic Labels
// =============================================================================

M("Airline Rank by On Time",
  "IF( NOT ISBLANK( [On Time % (Completed)] ),\n"
+ "    RANKX( ALLSELECTED( airlines[AIRLINE] ),\n"
+ "           [On Time % (Completed)], , DESC, DENSE ) )",
  "07 Ranking & Labels", "0",
  "ALLSELECTED, not ALL: with ALL, a user who filters to five airlines still "
+ "sees ranks out of fourteen, which reads as a bug to them. If a visual "
+ "displays [Airline Display] instead of [Airline Name], this collapses to 1 on "
+ "every row - use ALLSELECTED( Airlines ) to be display-column agnostic.");

M("Airport Rank by On Time",
  "IF( NOT ISBLANK( [On Time % (Completed)] ),\n"
+ "    RANKX( ALLSELECTED( airports[AIRPORT] ),\n"
+ "           [On Time % (Completed)], , DESC, DENSE ) )",
  "07 Ranking & Labels", "0", "");

M("Best Airline",
  "VAR Ranked =\n"
+ "    FILTER(\n"
+ "        ADDCOLUMNS( ALLSELECTED( airlines[AIRLINE] ),\n"
+ "            \"@OTP\", [On Time % (Completed)],\n"
+ "            \"@Vol\", [Total Flights] ),\n"
+ "        NOT ISBLANK( [@OTP] ) && [@Vol] >= [Min Flights For Ranking] )\n"
+ "RETURN MAXX( TOPN( 1, Ranked, [@OTP], DESC ), airlines[AIRLINE] )",
  "07 Ranking & Labels", "",
  "Returns a NAME for a card visual.");

M("Worst Airline",
  "VAR Ranked =\n"
+ "    FILTER(\n"
+ "        ADDCOLUMNS( ALLSELECTED( airlines[AIRLINE] ),\n"
+ "            \"@OTP\", [On Time % (Completed)],\n"
+ "            \"@Vol\", [Total Flights] ),\n"
+ "        NOT ISBLANK( [@OTP] ) && [@Vol] >= [Min Flights For Ranking] )\n"
+ "RETURN MINX( TOPN( 1, Ranked, [@OTP], ASC ), airlines[AIRLINE] )",
  "07 Ranking & Labels", "",
  "The NOT ISBLANK guard is load-bearing. BLANK sorts BELOW every real value in "
+ "an ascending TOPN, so without it any airline excluded by a slicer is "
+ "reported to the executive as the worst performing airline. That defect "
+ "survives testing and fails in a board meeting.");

M("Top Delay Cause",
  "VAR Causes =\n"
+ "    DATATABLE( \"Cause\", STRING,\n"
+ "        { {\"Late Aircraft\"}, {\"Airline\"}, {\"Air System\"},\n"
+ "          {\"Weather\"}, {\"Security\"} } )\n"
+ "VAR Minutes =\n"
+ "    ADDCOLUMNS( Causes, \"@Min\",\n"
+ "        SWITCH( [Cause],\n"
+ "            \"Late Aircraft\", [Late Aircraft Delay Min],\n"
+ "            \"Airline\",       [Airline Delay Min],\n"
+ "            \"Air System\",    [Air System Delay Min],\n"
+ "            \"Weather\",       [Weather Delay Min],\n"
+ "            \"Security\",      [Security Delay Min] ) )\n"
+ "RETURN MAXX( TOPN( 1, Minutes, [@Min], DESC ), [Cause] )",
  "07 Ranking & Labels", "",
  "Dynamic card naming the dominant driver for whatever the user has sliced to. "
+ "Re-ranks live as they filter by airport, month or carrier. Evaluates five "
+ "measures per row - fine on a card, do not put it in a matrix.");

M("KPI Status Colour",
  "VAR Actual = [On Time % (Completed)]\n"
+ "RETURN SWITCH( TRUE(),\n"
+ "    ISBLANK( Actual ),             \"#546077\",\n"
+ "    Actual >= [Target OTP],        \"#2E7D32\",\n"
+ "    Actual >= [Target OTP] - 0.05, \"#F9A825\",\n"
+ "    \"#C62828\" )",
  "07 Ranking & Labels", "",
  "Apply via Conditional formatting > Font colour > Format style: Field value. "
+ "BLANK renders neutral grey rather than alarming red, so October reads as "
+ "\"no data\" instead of \"catastrophic month\".");

M("Data Coverage Note",
  "VAR MonthsWithData =\n"
+ "    CALCULATE( DISTINCTCOUNT( 'Date Table'[Year Month] ),\n"
+ "        FILTER( ALL( 'Date Table' ), [Total Flights] > 0 ) )\n"
+ "VAR FirstDate = CALCULATE( MIN( flights[Flight Date] ), ALL( flights ) )\n"
+ "VAR LastDate  = CALCULATE( MAX( flights[Flight Date] ), ALL( flights ) )\n"
+ "RETURN\n"
+ "    \"Coverage: \" & FORMAT( FirstDate, \"MMM yyyy\" ) & \" - \"\n"
+ "        & FORMAT( LastDate, \"MMM yyyy\" ) & \" | \" & MonthsWithData\n"
+ "        & \" months with data | October 2015 is absent from the source extract.\"",
  "07 Ranking & Labels", "",
  "Derived, not hardcoded: a hardcoded caveat goes stale at the first refresh, "
+ "and a stale caveat is worse than none. Place on every page. Never let a "
+ "stakeholder discover a data gap themselves in the middle of a meeting.");


// =============================================================================
//  08 Validation  -  all four must read exactly 0 after every refresh
// =============================================================================

M("Check Status Sum",
  "[Total Flights] - ( [On Time Flights] + [Delayed Flights]\n"
+ "                  + [Cancelled Flights] + [Diverted Flights] )",
  "08 Validation", "#,0", "MUST BE 0. The four statuses must partition the table.");

M("Check Rate Sum",
  "ROUND( [On Time % (Completed)] + [Delay Rate %] - 1, 6 )",
  "08 Validation", "0.000000",
  "MUST BE 0. On-time and delay rates share a denominator and must sum to 100%.");

M("Check Cancel Codes",
  "[Cancelled Flights] - ( [Weather Cancellations] + [Carrier Cancellations]\n"
+ "                      + [Air System Cancellations] + [Security Cancellations] )",
  "08 Validation", "#,0", "MUST BE 0. The four codes must reconcile to 28,570.");

M("Check Attribution",
  "[Total Attributed Delay Min] - ( [Air System Delay Min] + [Security Delay Min]\n"
+ "    + [Airline Delay Min] + [Late Aircraft Delay Min] + [Weather Delay Min] )",
  "08 Validation", "#,0", "MUST BE 0.");


// =============================================================================
//  Report
// =============================================================================

Info("Measure deployment complete.\n\n"
   + "  Created : " + created + "\n"
   + "  Updated : " + updated + "\n"
   + "  Total   : " + t.Measures.Count + " measures in " + tableName + "\n\n"
   + "NEXT:\n"
   + "  1. File > Save (Ctrl+S) here in Tabular Editor.\n"
   + "  2. Return to Power BI - the measures will be there.\n"
   + "  3. Build a validation page and confirm the four Check measures\n"
   + "     under '08 Validation' all read exactly 0.\n\n"
   + "If any Check is non-zero, stop and read the diagnosis table at the\n"
   + "bottom of docs/rebuild-guide.md before publishing anything.");
