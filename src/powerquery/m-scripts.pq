/* =============================================================================
   FLIGHT OPERATIONS INTELLIGENCE 2015 — POWER QUERY (M) SCRIPTS
   5 queries: Airlines · Airports · Cancellation Codes · Flights · Date Table
   -----------------------------------------------------------------------------
   HOW TO USE
     1. Power BI Desktop > Home > Transform data
     2. Home > Manage Parameters > New — create SourceFolder (STEP 0) FIRST
     3. Home > New Source > Blank Query > View > Advanced Editor > paste > Done
     4. Rename each query to the name in its header. Those names are a contract
        consumed by src/dax/measures.dax — they are not cosmetic.

   NAMING POLICY — RAW PHYSICAL NAMES EVERYWHERE
     flights              raw CSV names, plus the derived columns this file adds
     airlines             IATA_CODE, AIRLINE          (AIRLINE = full name)
     airports             IATA_CODE, AIRPORT, CITY, STATE, COUNTRY,
                          LATITUDE, LONGITUDE
     cancellation_codes   CANCELLATION_REASON, CANCELLATION_DESCRIPTION

   No query renames a column. That is deliberate, and it matches the live model.

   For friendly labels in the report, set DISPLAY NAMES in Model view
   (select the column > Properties > Name). Display names change what the reader
   sees; they do not rebind DAX. Renaming in Power Query DOES rebind, and breaks
   every measure in src/dax/measures.dax silently at the next refresh.

   An earlier draft of this file renamed the dimension columns
   (IATA_CODE -> Airline Code, AIRPORT -> Airport Name, and so on) and added
   Airline Short Name and Airport Label. Those steps were never applied to the
   model, so this document described a model that did not exist — which is how a
   review came to "correct" a working measure library into a broken one.
   See docs/REVIEW-CORRECTION.md.

   A document describing a model is not a model. If you change a name here,
   change it in the model and in src/dax/measures.dax in the same commit.

   TRAP WORTH KNOWING
     flights[AIRLINE]   = the two-letter IATA code   ("DL")
     airlines[AIRLINE]  = the full carrier name      ("Delta Air Lines Inc.")
   Same column name, two different things, in a related pair of tables. Always
   qualify the table in DAX.
   ============================================================================= */


/* =============================================================================
   STEP 0  ///  PARAMETER — create before anything else
   -----------------------------------------------------------------------------
   Home > Manage Parameters > New Parameter
       Name          : SourceFolder
       Type          : Text
       Suggested     : Any value
       Current Value : the folder on YOUR machine holding the CSVs
                       (include the trailing backslash)

   Every query resolves against this one value. A contributor clones the repo,
   sets one parameter, refreshes. Nothing about anyone's filesystem, employer or
   username ships to the repository.
   ============================================================================= */

// SourceFolder = "C:\path\to\data\" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]


/* =============================================================================
   QUERY 1  ///  airlines            dimension, 14 rows
   ============================================================================= */

let
    Source = Csv.Document(
        File.Contents( SourceFolder & "airlines.csv" ),
        [Delimiter=",", Columns=2, Encoding=65001, QuoteStyle=QuoteStyle.Csv] ),
    Promoted = Table.PromoteHeaders( Source, [PromoteAllScalars=true] ),
    Final = Table.TransformColumnTypes( Promoted, {
        {"IATA_CODE", type text}, {"AIRLINE", type text} })
in
    Final

// Produces exactly two columns: IATA_CODE and AIRLINE. No renames, no derived
// columns — this matches the live model.
//
// OPTIONAL, NOT APPLIED: a short display label for chart axes.
// If you ever want one, add it as an explicit 14-row lookup, never as chained
// Text.Replace on the suffixes. Stripping " Inc." / " Co." / " Airlines" in
// sequence looks clever and produces an inconsistent axis, because three
// carriers spell it "Air Lines" as two words and the suffix survives for them:
//     American Airlines Inc. -> "American"
//     United Air Lines Inc.  -> "United Air Lines"
//     Delta Air Lines Inc.   -> "Delta Air Lines"
// Fourteen rows is small enough to name by hand. On a dimension this size, be
// correct rather than clever.
//
// For most cases you do not need a new column at all: set a Display name on
// AIRLINE in Model view and leave the data alone.


/* =============================================================================
   QUERY 2  ///  Airports            dimension, 10 rows, ORIGIN only
   -----------------------------------------------------------------------------
   DESIGN DECISION: this dimension serves ORIGIN_AIRPORT only.
   DESTINATION_AIRPORT holds 273 distinct values and airports.csv covers only
   the 10 origin hubs, so destination stays an unrelated text attribute.

   THE COST IS VISIBLE IN THE REPORT: the top-routes table renders
   "Los Angeles -> JFK" — origin resolves to a city, destination falls back to a
   raw code. Documented in docs/model-design.md with the v1.1 upgrade path
   (full 322-row airport reference + role-playing dimension + USERELATIONSHIP).
   ============================================================================= */

let
    Source = Csv.Document(
        File.Contents( SourceFolder & "airports.csv" ),
        [Delimiter=",", Columns=7, Encoding=65001, QuoteStyle=QuoteStyle.Csv] ),
    Promoted = Table.PromoteHeaders( Source, [PromoteAllScalars=true] ),
    Typed = Table.TransformColumnTypes( Promoted, {
        {"IATA_CODE", type text}, {"AIRPORT",   type text},
        {"CITY",      type text}, {"STATE",     type text},
        {"COUNTRY",   type text}, {"LATITUDE",  type number},
        {"LONGITUDE", type number} }),
    Final = Typed
in
    Final

// Produces the seven raw columns: IATA_CODE, AIRPORT, CITY, STATE, COUNTRY,
// LATITUDE, LONGITUDE. No renames, no derived label — this matches the live
// model.
//
// AFTER LOADING, set the data categories:
//   LATITUDE -> Latitude · LONGITUDE -> Longitude · STATE -> State or Province
// Without them, map visuals geocode by name and can plot a US airport on the
// wrong continent. This is the one post-load step that genuinely matters.


/* =============================================================================
   QUERY 3  ///  Cancellation Codes  dimension, 5 rows
   ============================================================================= */

let
    Source = Csv.Document(
        File.Contents( SourceFolder & "cancellation_codes.csv" ),
        [Delimiter=",", Columns=2, Encoding=65001, QuoteStyle=QuoteStyle.Csv] ),
    Promoted = Table.PromoteHeaders( Source, [PromoteAllScalars=true] ),
    Typed = Table.TransformColumnTypes( Promoted, {
        {"CANCELLATION_REASON",      type text},
        {"CANCELLATION_DESCRIPTION", type text} }),
    // Table.Combine, not Table.InsertRows with a hardcoded index — no
    // positional dependency, so it survives a change to the source file.
    NotCancelled = #table(
        type table [CANCELLATION_REASON = text, CANCELLATION_DESCRIPTION = text],
        {{"N", "Not Cancelled"}} ),
    Final = Table.Combine( {Typed, NotCancelled} )
in
    Final

// NOTE ON THE COLUMN NAMES: CANCELLATION_REASON holds the CODE (A/B/C/D/N) and
// CANCELLATION_DESCRIPTION holds the text. The name says "reason" but carries
// the code — a quirk of the source file, kept as-is. If it confuses report
// readers, set a Display name of "Cancellation Code" in Model view rather than
// renaming the column here.

// WHY THE 5th MEMBER: 98.5% of fact rows are not cancelled. Without an "N"
// member they resolve to a (Blank) row in every slicer and legend. Adding the
// member is the correct fix; hiding the blank in the visual is not.


/* =============================================================================
   QUERY 4  ///  Flights             FACT, 1,949,742 rows
   -----------------------------------------------------------------------------
   THE MOST IMPORTANT DECISION IN THIS FILE, stated up front:
   the NULLs in the five delay-reason columns are LEFT AS NULL. They are
   structurally absent — populated only when arrival delay >= 15 min, on 390,262
   of 1,949,742 rows (79.98% NULL). Zero-filling them makes every AVERAGE-based
   attribution measure divide by 1.9M instead of 390k and understates each cause
   by roughly a factor of five.
   ============================================================================= */

let
    Source = Csv.Document(
        File.Contents( SourceFolder & "flights.csv" ),
        [Delimiter=",", Columns=32, Encoding=65001, QuoteStyle=QuoteStyle.Csv] ),

    // --- 1. Drop the ghost index column BEFORE promoting headers -------------
    // The CSV's first header cell is empty, and its values run 1..5,819,074 —
    // evidence that this file is a 10-airport subset of the full 5.8M-row
    // source. Removing it while still in raw Csv.Document form avoids ending up
    // with a column whose name is an empty string, which cannot be referenced.
    RemovedIndex = Table.RemoveColumns( Source, {"Column1"} ),
    Promoted     = Table.PromoteHeaders( RemovedIndex, [PromoteAllScalars=true] ),

    // --- 2. Types -----------------------------------------------------------
    // Numeric fields arrive as "2.0", "-8.0". Int64.Type parses and rounds them
    // correctly, and since every source value has a ".0" fraction the rounding
    // is a no-op. Revisit this step before trusting totals if you ever repoint
    // the query at a source with true decimals.
    Typed = Table.TransformColumnTypes( Promoted, {
        {"YEAR", Int64.Type}, {"MONTH", Int64.Type}, {"DAY", Int64.Type},
        {"DAY_OF_WEEK", Int64.Type},
        {"AIRLINE", type text}, {"FLIGHT_NUMBER", Int64.Type},
        {"TAIL_NUMBER", type text},
        {"ORIGIN_AIRPORT", type text}, {"DESTINATION_AIRPORT", type text},
        {"SCHEDULED_DEPARTURE", Int64.Type}, {"DEPARTURE_TIME", Int64.Type},
        {"DEPARTURE_DELAY", Int64.Type}, {"TAXI_OUT", Int64.Type},
        {"WHEELS_OFF", Int64.Type}, {"SCHEDULED_TIME", Int64.Type},
        {"ELAPSED_TIME", Int64.Type}, {"AIR_TIME", Int64.Type},
        {"DISTANCE", Int64.Type}, {"WHEELS_ON", Int64.Type},
        {"TAXI_IN", Int64.Type}, {"SCHEDULED_ARRIVAL", Int64.Type},
        {"ARRIVAL_TIME", Int64.Type}, {"ARRIVAL_DELAY", Int64.Type},
        {"DIVERTED", Int64.Type}, {"CANCELLED", Int64.Type},
        {"CANCELLATION_REASON", type text},
        {"AIR_SYSTEM_DELAY", Int64.Type}, {"SECURITY_DELAY", Int64.Type},
        {"AIRLINE_DELAY", Int64.Type}, {"LATE_AIRCRAFT_DELAY", Int64.Type},
        {"WEATHER_DELAY", Int64.Type} }),

    // --- 3. Flight Date -----------------------------------------------------
    FlightDate = Table.AddColumn( Typed, "Flight Date",
        each #date([YEAR], [MONTH], [DAY]), type date ),

    // --- 4. HHMM -> time. 2400 is not a valid time; it means midnight. -------
    fnTime = (t as nullable number) as nullable time =>
        if t = null then null
        else if t = 2400 then #time(0, 0, 0)
        else #time( Number.IntegerDivide(t, 100), Number.Mod(t, 100), 0 ),

    TimeCols = Table.TransformColumns( FlightDate, {
        {"SCHEDULED_DEPARTURE", fnTime, type time},
        {"DEPARTURE_TIME",      fnTime, type time},
        {"WHEELS_OFF",          fnTime, type time},
        {"WHEELS_ON",           fnTime, type time},
        {"SCHEDULED_ARRIVAL",   fnTime, type time},
        {"ARRIVAL_TIME",        fnTime, type time} }),

    // --- 5. Departure hour bucket -------------------------------------------
    // Null-guarded although SCHEDULED_DEPARTURE is never null in DOT data:
    // Time.Hour(null) throws, and a throw here fails the entire refresh.
    DepHour = Table.AddColumn( TimeCols, "Departure Hour",
        each if [SCHEDULED_DEPARTURE] = null then null
             else Time.Hour([SCHEDULED_DEPARTURE]), Int64.Type ),

    // --- 6. Complete the cancellation key -----------------------------------
    FixCancelKey = Table.ReplaceValue( DepHour, null, "N",
        Replacer.ReplaceValue, {"CANCELLATION_REASON"} ),

    // --- 7. Flight Status — THE SINGLE SOURCE OF TRUTH ----------------------
    //  THE THRESHOLD IS >= 15, NOT > 15.
    //  US DOT counts a flight as on time only if it arrives LESS THAN 15 minutes
    //  late. The data agrees: the five reason columns are populated on exactly
    //  390,262 rows and the minimum ARRIVAL_DELAY among them is 15.
    //  Using "> 15" moves the 14,206 flights that arrived exactly 15 minutes
    //  late into On Time and inflates the on-time count by that exact amount.
    //
    //  NOTHING ELSE IN THIS PROJECT MAY CLASSIFY A FLIGHT. Every downstream
    //  artefact — DAX, the HTML dashboard, the validation script — reads this
    //  column or reimplements this exact rule from scripts/build_dashboard.py.
    //  A classification rule written twice will diverge; that is precisely how
    //  the v1 dashboard came to disagree with the v1 measures.
    //
    //  The null branch is defensive: `null >= 15` evaluates to null, and
    //  `if null then` raises "We cannot convert the value null to type Logical",
    //  which fails the whole refresh. Today every operated flight has a non-null
    //  ARRIVAL_DELAY — verified, the N/A band holds exactly 28,570 + 5,006 rows
    //  — so the guard never fires. It exists so that a future extract cannot
    //  break the refresh silently. Assert its count is 0 after every load.
    Status = Table.AddColumn( FixCancelKey, "Flight Status", each
        if [CANCELLED] = 1 then "Cancelled"
        else if [DIVERTED] = 1 then "Diverted"
        else if [ARRIVAL_DELAY] = null then "Unknown"
        else if [ARRIVAL_DELAY] >= 15 then "Delayed"
        else "On Time", type text ),

    // --- 8. Delay severity bands. Labels match the boundaries exactly. ------
    Severity = Table.AddColumn( Status, "Delay Band", each
        if [ARRIVAL_DELAY] = null then "N/A"
        else if [ARRIVAL_DELAY] < 15   then "On Time (<15 min)"
        else if [ARRIVAL_DELAY] <= 45  then "Minor (15-45 min)"
        else if [ARRIVAL_DELAY] <= 120 then "Major (46-120 min)"
        else "Severe (>120 min)", type text ),
    // Expect N/A = 33,576 = 28,570 cancelled + 5,006 diverted.

    // --- 9. Delay Recovery: minutes made up in the air ----------------------
    Recovery = Table.AddColumn( Severity, "Delay Recovery", each
        if [DEPARTURE_DELAY] = null or [ARRIVAL_DELAY] = null then null
        else [DEPARTURE_DELAY] - [ARRIVAL_DELAY], Int64.Type ),

    // --- 10. Distance band. Note the boundary: exactly 1500 is Long Haul. ---
    DistBand = Table.AddColumn( Recovery, "Distance Band", each
        if [DISTANCE] < 500       then "Short Haul (<500 mi)"
        else if [DISTANCE] < 1500 then "Medium Haul (500-1499 mi)"
        else "Long Haul (>=1500 mi)", type text ),

    // --- 11. Drop redundant columns -----------------------------------------
    // YEAR is constant; MONTH/DAY/DAY_OF_WEEK are all derivable from the date
    // dimension once Flight Date exists.
    Trimmed = Table.RemoveColumns( DistBand,
        {"YEAR", "MONTH", "DAY", "DAY_OF_WEEK"} ),

    // --- 12. Drop what no visual consumes — the largest VertiPaq saving -----
    // Of the six `time` columns only SCHEDULED_DEPARTURE is used (it feeds
    // Departure Hour). TAIL_NUMBER (~4,900 distinct) and FLIGHT_NUMBER (~6,900)
    // are high-cardinality columns that no visual reads — pure dictionary cost
    // across 1.9M rows.
    //
    // COMMENT THIS STEP OUT if you add aircraft-utilisation analysis:
    // TAIL_NUMBER is the only route to fleet-level insight in this dataset.
    //
    // Measure the effect with DAX Studio > View Metrics before and after.
    // Record both figures in the README. An optimisation claim without a
    // measurement is just an opinion.
    Final = Table.RemoveColumns( Trimmed, {
        "DEPARTURE_TIME", "WHEELS_OFF", "WHEELS_ON",
        "ARRIVAL_TIME",   "SCHEDULED_ARRIVAL",
        "TAIL_NUMBER",    "FLIGHT_NUMBER" })
in
    Final


/* =============================================================================
   QUERY 5  ///  Date Table
   -----------------------------------------------------------------------------
   Built in M rather than as a DAX calculated table, and the range is derived
   from the fact table rather than hardcoded:
     - a DAX calculated table cannot participate in incremental refresh and is
       invisible to Power Query lineage view
     - a hardcoded CALENDAR(2015-01-01, 2015-12-31) silently truncates the model
       the day someone adds 2016 data
   Continuous calendar including October, even though October has no flights —
   a gap-free date table is required for correct time intelligence.
   ============================================================================= */

let
    MinDate  = Date.StartOfYear( List.Min( Flights[Flight Date] ) ),
    MaxDate  = Date.EndOfYear(   List.Max( Flights[Flight Date] ) ),
    DayCount = Duration.Days( MaxDate - MinDate ) + 1,
    Dates    = List.Dates( MinDate, DayCount, #duration(1,0,0,0) ),
    ToTable  = Table.FromList( Dates, Splitter.SplitByNothing(), {"Date"} ),
    Typed    = Table.TransformColumnTypes( ToTable, {{"Date", type date}} ),

    C1  = Table.AddColumn( Typed, "Year",         each Date.Year([Date]), Int64.Type ),
    C2  = Table.AddColumn( C1,    "Month Number", each Date.Month([Date]), Int64.Type ),
    C3  = Table.AddColumn( C2,    "Month Name",   each Date.MonthName([Date], "en-US"), type text ),
    C4  = Table.AddColumn( C3,    "Month Short",  each Text.Start( Date.MonthName([Date], "en-US"), 3 ), type text ),
    C5  = Table.AddColumn( C4,    "Year Month",   each Date.ToText([Date], "yyyy-MM"), type text ),
    C6  = Table.AddColumn( C5,    "Quarter",      each "Q" & Text.From( Date.QuarterOfYear([Date]) ), type text ),
    C7  = Table.AddColumn( C6,    "Day",          each Date.Day([Date]), Int64.Type ),
    C8  = Table.AddColumn( C7,    "Day Name",     each Date.DayOfWeekName([Date], "en-US"), type text ),
    C9  = Table.AddColumn( C8,    "Day Short",    each Text.Start( Date.DayOfWeekName([Date], "en-US"), 3 ), type text ),

    // ISO weekday: 1 = Monday .. 7 = Sunday.
    // The source DAY_OF_WEEK column uses this same ISO convention. Power BI's
    // default WEEKDAY() starts at Sunday = 1; mixing the two silently shifts
    // every day-of-week chart by one position.
    C10 = Table.AddColumn( C9,  "ISO Weekday",  each Date.DayOfWeek([Date], Day.Monday) + 1, Int64.Type ),
    C11 = Table.AddColumn( C10, "Week of Year", each Date.WeekOfYear([Date], Day.Monday), Int64.Type ),
    C12 = Table.AddColumn( C11, "Is Weekend",   each if Date.DayOfWeek([Date], Day.Monday) >= 5 then "Weekend" else "Weekday", type text ),
    C13 = Table.AddColumn( C12, "Season",       each
            if List.Contains({12,1,2}, Date.Month([Date])) then "Winter"
            else if List.Contains({3,4,5}, Date.Month([Date])) then "Spring"
            else if List.Contains({6,7,8}, Date.Month([Date])) then "Summer"
            else "Fall", type text ),

    // Data-driven, not hardcoded to "month 10". If the extract is ever repaired
    // and October arrives, this flag corrects itself instead of flagging a gap
    // that no longer exists.
    MonthsPresent = List.Distinct(
        List.Transform( Flights[Flight Date], each Date.ToText(_, "yyyy-MM") ) ),
    C14 = Table.AddColumn( C13, "Has Flight Data", each
            if List.Contains( MonthsPresent, Date.ToText([Date], "yyyy-MM") )
            then "Has Data" else "No Data", type text ),

    Final = C14
in
    Final

// AFTER LOADING:
//   1. Modeling > Mark as Date Table > [Date]
//      Required for DATEADD and DATESINPERIOD to behave correctly.
//   2. Sort "Month Name" by "Month Number"
//   3. Sort "Day Name"   by "ISO Weekday"
//
// PLANNED FOR v1.1: a US federal holiday flag. Thanksgiving, Christmas and
// July 4th drive a large share of the delay variance here, and a holiday flag
// turns "December is bad" into "the eight days around Christmas are bad" —
// a staffing decision rather than a seasonal shrug.


/* =============================================================================
   RELATIONSHIPS — star schema, all single-direction, dimension filters fact
   =============================================================================

     'Date Table'[Date]                     1 --> *  flights[Flight Date]
     airlines[IATA_CODE]                    1 --> *  flights[AIRLINE]
     airports[IATA_CODE]                    1 --> *  flights[ORIGIN_AIRPORT]
     cancellation_codes[CANCELLATION_REASON] 1 --> * flights[CANCELLATION_REASON]

   Note that airlines[IATA_CODE] joins to flights[AIRLINE]: the fact table holds
   the code in a column named AIRLINE, while the dimension holds the code in
   IATA_CODE and the full name in AIRLINE. Confusing, but it is what the source
   files provide — and now it is written down.

   flights[DESTINATION_AIRPORT] has NO relationship — see Query 2.

   Do not enable bi-directional filtering on any of these. With one 1.9M-row
   fact and four small dimensions there is no scenario in this model that needs
   it, and it introduces filter ambiguity the moment a fifth table is added.

   =============================================================================
   QUERY FOLDING & INCREMENTAL REFRESH — the honest answer
   =============================================================================

   FOLDING: none, and none is achievable. Csv.Document is a file connector with
   no query engine behind it to push work down to. Every step above executes in
   the mashup engine over the full 1.9M rows. Step ORDER still matters for local
   performance — dropping the index column before promoting headers, and
   removing unused columns last, are both deliberate — but "check the folding
   indicator" does not apply to this source and must not be claimed anywhere.

   INCREMENTAL REFRESH: not viable on this source. RangeStart/RangeEnd only pay
   off when the filter FOLDS. Against a CSV, Power BI reads the entire file and
   then discards rows: you pay full I/O and gain only partition complexity.

   To enable it, change the source, not the settings:
     A (lightest)  partition flights.csv into monthly Parquet files and point a
                   Folder query at them. Still no folding, but refresh I/O drops
                   by roughly 11/12.
     B (correct)   land the data in SQL Server / Azure SQL / Fabric Warehouse.
                   RangeStart/RangeEnd then fold to a WHERE clause.
     C (strategic) Fabric Lakehouse + Direct Lake. No import, no refresh window.

   For a static 2015 archive that will never receive new rows, A is sufficient
   and B/C are over-engineering. The README says so plainly rather than implying
   an enterprise pipeline this project does not have.

   =============================================================================
   POST-REFRESH VALIDATION CHECKLIST
   =============================================================================

   [ ] Flights row count = 1,949,742
   [ ] Flight Status distribution:
           On Time    1,525,904      Delayed    390,262
           Cancelled     28,570      Diverted     5,006
   [ ] "Unknown" status count = 0.
       If not, ARRIVAL_DELAY has nulls on operated flights and every punctuality
       denominator in the model needs revisiting before anything is published.
   [ ] Month slicer shows 11 months — October is legitimately absent
   [ ] Delay Band "N/A" = 33,576
   [ ] Cancellation codes reconcile: B 16,372 + A 8,084 + C 4,112 + D 2 = 28,570
   [ ] Cancellation Codes shows 5 members including "Not Cancelled"
   [ ] No (Blank) member on any dimension
   [ ] Time column renders as HH:MM:SS, no value equals 24:00:00
   [ ] Departure Hour: 22 distinct values, NOT 24.
       Hours 03 and 04 hold zero flights across all ten hubs. This is real, not
       a defect — but a categorical X-axis will silently omit both and make the
       overnight trough look continuous. Use a continuous axis, or build a
       24-row hour dimension and left-join to it.
   [ ] Delay-reason columns still contain NULLs, not zeros — 79.98% null
   [ ] Model size recorded from DAX Studio > View Metrics. Measured, not
       estimated.

   ============================================================================= */
