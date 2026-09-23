import streamlit as st
import pandas as pd
from io import BytesIO

# ============================================================
# SOC 2 CONTROL TESTING SYSTEM
# ============================================================

st.set_page_config(
    page_title="SOC 2 Control Testing",
    page_icon="🔐",
    layout="wide"
)

# ============================================================
# SESSION STATE
# ============================================================

if "data" not in st.session_state:
    st.session_state.data = None

if "results" not in st.session_state:
    st.session_state.results = {}

if "sheet_name" not in st.session_state:
    st.session_state.sheet_name = ""

# ============================================================
# HEADER
# ============================================================

st.title("🔐 SOC 2 Control Testing System")

st.caption(
    "Test a control once and synchronize the result "
    "across CC, A, C, P and PI criteria."
)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("📁 Audit Workbook")

    uploaded_file = st.file_uploader(
        "Upload SOC 2 Excel workbook",
        type=["xlsx", "xls"]
    )

# ============================================================
# UPLOAD EXCEL
# ============================================================

if uploaded_file:

    try:

        file_bytes = uploaded_file.read()

        excel = pd.ExcelFile(
            BytesIO(file_bytes)
        )

        st.sidebar.success(
            "Workbook loaded successfully."
        )

        selected_sheet = st.sidebar.selectbox(
            "Select worksheet",
            excel.sheet_names
        )

        if st.sidebar.button(
            "Load Worksheet",
            type="primary"
        ):

            df = pd.read_excel(
                BytesIO(file_bytes),
                sheet_name=selected_sheet
            )

            st.session_state.data = df
            st.session_state.sheet_name = selected_sheet

            st.session_state.results = {}

            st.rerun()

    except Exception as e:

        st.error(
            f"Unable to read workbook: {e}"
        )


# ============================================================
# MAIN APPLICATION
# ============================================================

if st.session_state.data is not None:

    df = st.session_state.data.copy()

    st.divider()

    # ========================================================
    # COLUMN CONFIGURATION
    # ========================================================

    st.header("⚙️ Configure Your Excel Columns")

    st.write(
        "Select the columns containing your existing SOC 2 information."
    )

    columns = list(df.columns)

    c1, c2 = st.columns(2)

    with c1:

        trust_id_column = st.selectbox(
            "Existing Trust ID / TSC ID column",
            columns,
            key="trust_id_column"
        )

    with c2:

        control_column = st.selectbox(
            "Control Description column",
            columns,
            key="control_column"
        )

    c3, c4 = st.columns(2)

    with c3:

        tsc_description_column = st.selectbox(
            "TSC Description column",
            columns,
            key="tsc_description_column"
        )

    with c4:

        test_column = st.selectbox(
            "Auditor Test / Test Procedure column",
            columns,
            key="test_column"
        )

    # ========================================================
    # CLEAN DATA
    # ========================================================

    for column in [
        trust_id_column,
        control_column,
        tsc_description_column,
        test_column
    ]:

        df[column] = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    # ========================================================
    # TRUST CATEGORY
    # ========================================================

    st.divider()

    st.header("🏷️ Trust Services Criteria")

    st.write(
        "Select the Trust Services Criteria category you want to work with."
    )

    trust_categories = [
        "CC",
        "A",
        "C",
        "P",
        "PI"
    ]

    selected_category = st.radio(
        "Criteria Category",
        trust_categories,
        horizontal=True
    )

    category_description = {

        "CC":
            "Common Criteria – Security",

        "A":
            "Availability",

        "C":
            "Confidentiality",

        "P":
            "Privacy",

        "PI":
            "Processing Integrity"
    }

    st.info(
        f"Selected: **{selected_category}** — "
        f"{category_description[selected_category]}"
    )

    # ========================================================
    # FILTER TRUST IDs
    # ========================================================

    category_rows = df[
        df[trust_id_column]
        .str.upper()
        .str.startswith(selected_category)
    ]

    # ========================================================
    # DASHBOARD
    # ========================================================

    st.divider()

    st.header("📊 Audit Dashboard")

    total_rows = len(category_rows)

    unique_controls = (
        category_rows[control_column]
        .replace("", pd.NA)
        .dropna()
        .nunique()
    )

    tested_controls = len(
        st.session_state.results
    )

    ineffective_controls = sum(
        1
        for value in st.session_state.results.values()
        if value.get("result") == "Exceptions Noted"
    )

    d1, d2, d3, d4 = st.columns(4)

    d1.metric(
        "Criteria Rows",
        total_rows
    )

    d2.metric(
        "Unique Controls",
        unique_controls
    )

    d3.metric(
        "Controls Tested",
        tested_controls
    )

    d4.metric(
        "Exceptions",
        ineffective_controls
    )

    # ========================================================
    # CONTROL SELECTION
    # ========================================================

    st.divider()

    st.header("🧪 Control Testing")

    all_controls = sorted(
        [
            x for x in category_rows[control_column].unique()
            if x
        ]
    )

    search = st.text_input(
        "🔎 Search Control",
        placeholder="Type part of a control description..."
    )

    filtered_controls = [
        control
        for control in all_controls
        if search.lower() in control.lower()
    ]

    if not filtered_controls:

        st.warning(
            "No controls found."
        )

    else:

        selected_control = st.selectbox(
            "Select Control",
            filtered_controls
        )

        # ====================================================
        # FIND ALL OCCURRENCES OF CONTROL
        # ====================================================

        all_control_rows = df[
            df[control_column] == selected_control
        ]

        # ====================================================
        # FIND CRITERIA MAPPINGS
        # ====================================================

        mapped_rows = all_control_rows[
            all_control_rows[trust_id_column]
            .str.upper()
            .str.startswith(selected_category)
        ]

        # ====================================================
        # CONTROL INFORMATION
        # ====================================================

        st.subheader(
            "📌 Control Information"
        )

        st.markdown(
            f"**Control:** {selected_control}"
        )

        st.write(
            f"This control occurs "
            f"**{len(all_control_rows)} time(s)** "
            f"in the workbook."
        )

        # ====================================================
        # CRITERIA MAPPINGS
        # ====================================================

        st.markdown(
            "### Trust IDs mapped to this control"
        )

        if len(mapped_rows) > 0:

            for trust_id in mapped_rows[
                trust_id_column
            ].unique():

                st.write(
                    f"• **{trust_id}**"
                )

        # ====================================================
        # SHOW ALL CRITERIA OCCURRENCES
        # ====================================================

        with st.expander(
            "🔍 View all occurrences of this control"
        ):

            display_columns = [
                trust_id_column,
                tsc_description_column,
                control_column,
                test_column
            ]

            st.dataframe(
                all_control_rows[
                    display_columns
                ],
                use_container_width=True
            )

        # ====================================================
        # CENTRALIZED TEST
        # ====================================================

        st.divider()

        st.subheader(
            "🧪 Test This Control Once"
        )

        existing = st.session_state.results.get(
            selected_control
        )

        if existing:

            st.success(
                "This control has already been tested."
            )

            st.info(
                "Any change made here will be reflected "
                "in every occurrence of this control."
            )

        # ====================================================
        # RESULT
        # ====================================================

        result_options = [
            "No Exceptions Noted",
            "Exceptions Noted",
            "Not Applicable",
            "Unable to Test"
        ]

        default_result = (
            existing["result"]
            if existing
            else "No Exceptions Noted"
        )

        result = st.selectbox(
            "Results",
            result_options,
            index=result_options.index(
                default_result
            )
        )

        # ====================================================
        # EVIDENCE
        # ====================================================

        evidence = st.text_area(
            "Evidence Reviewed",
            value=(
                existing["evidence"]
                if existing
                else ""
            ),
            placeholder=(
                "Example: Load balancer configuration, "
                "AWS console screenshots, compliance "
                "platform evidence..."
            )
        )

        # ====================================================
        # AUDITOR TEST
        # ====================================================

        auditor_test = st.text_area(
            "Tests Performed by The Auditor",
            value=(
                existing["auditor_test"]
                if existing
                else ""
            ),
            placeholder=(
                "Describe the audit procedure performed..."
            )
        )

        # ====================================================
        # COMMENTS
        # ========================================================

        comments = st.text_area(
            "Auditor Comments",
            value=(
                existing["comments"]
                if existing
                else ""
            ),
            placeholder=(
                "Enter additional audit observations..."
            )
        )

        # ====================================================
        # SAVE RESULT
        # ========================================================

        if st.button(
            "💾 SAVE CONTROL TEST",
            type="primary",
            use_container_width=True
        ):

            st.session_state.results[
                selected_control
            ] = {

                "result":
                    result,

                "evidence":
                    evidence,

                "auditor_test":
                    auditor_test,

                "comments":
                    comments,

                "category":
                    selected_category,

                "trust_ids":
                    list(
                        all_control_rows[
                            trust_id_column
                        ].unique()
                    )
            }

            st.success(
                f"Control tested successfully: "
                f"{selected_control}"
            )

            st.rerun()

    # ========================================================
    # CENTRALIZED RESULTS
    # ========================================================

    st.divider()

    st.header(
        "📋 Centralized Control Results"
    )

    result_rows = []

    for control, result_data in (
        st.session_state.results.items()
    ):

        result_rows.append({

            "Control Description":
                control,

            "Trust Category":
                result_data["category"],

            "Trust IDs":
                ", ".join(
                    result_data["trust_ids"]
                ),

            "Results":
                result_data["result"],

            "Evidence":
                result_data["evidence"]
        })

    if result_rows:

        results_df = pd.DataFrame(
            result_rows
        )

        st.dataframe(
            results_df,
            use_container_width=True
        )

    else:

        st.info(
            "No controls tested yet."
        )

    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header(
        "📥 Generate SOC 2 Audit Excel"
    )

    if st.button(
        "Generate Final Excel",
        type="primary"
    ):

        output_df = df.copy()

        # ----------------------------------------------------
        # CREATE REQUIRED OUTPUT COLUMNS
        # ----------------------------------------------------

        output_df["Trust ID"] = (
            output_df[trust_id_column]
        )

        output_df["TSC Description"] = (
            output_df[
                tsc_description_column
            ]
        )

        output_df["Controls Description"] = (
            output_df[
                control_column
            ]
        )

        output_df[
            "Tests Performed by The Auditor"
        ] = (
            output_df[
                test_column
            ]
        )

        output_df["Results"] = ""

        # ----------------------------------------------------
        # APPLY CENTRALIZED RESULTS
        # ----------------------------------------------------

        for index, row in output_df.iterrows():

            control = row[
                control_column
            ]

            if control in st.session_state.results:

                result_data = (
                    st.session_state.results[
                        control
                    ]
                )

                output_df.at[
                    index,
                    "Results"
                ] = result_data[
                    "result"
                ]

                output_df.at[
                    index,
                    "Tests Performed by The Auditor"
                ] = result_data[
                    "auditor_test"
                ]

        # ----------------------------------------------------
        # FINAL OUTPUT COLUMNS
        # ----------------------------------------------------

        final_columns = [

            "Trust ID",

            "TSC Description",

            "Controls Description",

            "Tests Performed by The Auditor",

            "Results"
        ]

        final_df = output_df[
            final_columns
        ].copy()

        # ----------------------------------------------------
        # EXCEL CREATION
        # ----------------------------------------------------

        excel_output = BytesIO()

        with pd.ExcelWriter(
            excel_output,
            engine="openpyxl"
        ) as writer:

            # Main audit report

            final_df.to_excel(
                writer,
                index=False,
                sheet_name="SOC 2 Audit Results"
            )

            # Centralized control testing

            if result_rows:

                results_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Control Test Register"
                )

        excel_output.seek(0)

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        st.download_button(

            label="⬇️ Download Final SOC 2 Excel",

            data=excel_output,

            file_name=(
                "SOC2_Audit_Report.xlsx"
            ),

            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),

            use_container_width=True
        )

        st.success(
            "Your SOC 2 audit Excel has been generated."
        )

else:

    # ========================================================
    # WELCOME SCREEN
    # ========================================================

    st.info(
        "👈 Upload your SOC 2 Excel workbook "
        "from the sidebar to begin."
    )

    st.markdown(
        """
        ## How the system works

        ### 1️⃣ Upload

        Upload your existing SOC 2 workbook.

        ### 2️⃣ Select Trust Services Criteria

        Choose:

        - **CC — Common Criteria**
        - **A — Availability**
        - **C — Confidentiality**
        - **P — Privacy**
        - **PI — Processing Integrity**

        ### 3️⃣ Select a control

        The system finds every occurrence of that control.

        ### 4️⃣ Test once

        Enter the auditor's testing procedure,
        evidence and result once.

        ### 5️⃣ Synchronize

        The same result is automatically applied
        to every occurrence of that control.

        ### 6️⃣ Export

        Generate a clean SOC 2 audit workbook with:

        - Trust ID
        - TSC Description
        - Controls Description
        - Tests Performed by The Auditor
        - Results
        """
    )
