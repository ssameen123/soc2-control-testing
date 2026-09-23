import streamlit as st
import pandas as pd
from io import BytesIO

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="SOC 2 Control Testing System",
    page_icon="🔐",
    layout="wide"
)

# ============================================================
# TITLE
# ============================================================

st.title("🔐 SOC 2 Control Testing System")
st.caption(
    "Test each control once and automatically synchronize "
    "the result across all SOC 2 TSC occurrences."
)

# ============================================================
# SESSION STATE
# ============================================================

if "data" not in st.session_state:
    st.session_state.data = None

if "results" not in st.session_state:
    st.session_state.results = {}

if "sheet_name" not in st.session_state:
    st.session_state.sheet_name = None

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("📁 Upload Audit File")

    uploaded_file = st.file_uploader(
        "Upload SOC 2 Excel file",
        type=["xlsx", "xls"]
    )

# ============================================================
# FILE UPLOAD
# ============================================================

if uploaded_file:

    try:

        excel_data = uploaded_file.read()

        xls = pd.ExcelFile(
            BytesIO(excel_data)
        )

        st.sidebar.success(
            "Excel file loaded successfully."
        )

        # ----------------------------------------------------
        # SHEET SELECTION
        # ----------------------------------------------------

        selected_sheet = st.sidebar.selectbox(
            "Select worksheet",
            xls.sheet_names
        )

        if st.sidebar.button("Load Worksheet"):

            df = pd.read_excel(
                BytesIO(excel_data),
                sheet_name=selected_sheet
            )

            st.session_state.data = df
            st.session_state.sheet_name = selected_sheet

            st.session_state.results = {}

            st.rerun()

    except Exception as e:

        st.error(
            f"Unable to read Excel file: {e}"
        )

# ============================================================
# MAIN APPLICATION
# ============================================================

if st.session_state.data is not None:

    df = st.session_state.data

    st.divider()

    # ========================================================
    # COLUMN SELECTION
    # ========================================================

    st.subheader("⚙️ Column Configuration")

    col1, col2 = st.columns(2)

    with col1:

        control_column = st.selectbox(
            "Control ID column",
            df.columns
        )

    with col2:

        tsc_column = st.selectbox(
            "TSC / Criteria column",
            df.columns
        )

    # ========================================================
    # CLEAN CONTROL IDS
    # ========================================================

    df[control_column] = (
        df[control_column]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df[tsc_column] = (
        df[tsc_column]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    controls = sorted(
        [
            x for x in df[control_column].unique()
            if x
        ]
    )

    # ========================================================
    # DASHBOARD METRICS
    # ========================================================

    total_controls = len(controls)

    tested_controls = len(
        st.session_state.results
    )

    remaining_controls = (
        total_controls - tested_controls
    )

    exception_count = sum(
        1
        for x in st.session_state.results.values()
        if x["result"] == "Ineffective"
    )

    st.subheader("📊 Audit Dashboard")

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Unique Controls",
        total_controls
    )

    m2.metric(
        "Tested",
        tested_controls
    )

    m3.metric(
        "Remaining",
        remaining_controls
    )

    m4.metric(
        "Ineffective",
        exception_count
    )

    # ========================================================
    # CONTROL SEARCH
    # ========================================================

    st.divider()

    st.subheader("🔎 Control Testing")

    search = st.text_input(
        "Search Control ID",
        placeholder="Example: AC-01"
    )

    filtered_controls = [
        x for x in controls
        if search.lower() in x.lower()
    ]

    if not filtered_controls:

        st.warning(
            "No controls found."
        )

    else:

        selected_control = st.selectbox(
            "Select control",
            filtered_controls
        )

        # ====================================================
        # FIND ALL OCCURRENCES
        # ====================================================

        control_rows = df[
            df[control_column] == selected_control
        ]

        tscs = sorted(
            control_rows[tsc_column]
            .unique()
        )

        # ====================================================
        # CONTROL INFORMATION
        # ====================================================

        st.markdown(
            f"### Control: `{selected_control}`"
        )

        st.write(
            f"This control appears **{len(control_rows)} "
            f"time(s)** in the audit file."
        )

        st.markdown(
            "### 📌 SOC 2 TSC Occurrences"
        )

        for tsc in tscs:

            st.write(
                f"• **{tsc}**"
            )

        # ====================================================
        # SHOW CONTROL ROWS
        # ====================================================

        with st.expander(
            "View all occurrences"
        ):

            st.dataframe(
                control_rows,
                use_container_width=True
            )

        # ====================================================
        # EXISTING RESULT
        # ====================================================

        existing = st.session_state.results.get(
            selected_control
        )

        if existing:

            st.success(
                f"Already tested: "
                f"{existing['result']}"
            )

            st.info(
                "Changing this result will update "
                "every occurrence of this control."
            )

        # ====================================================
        # TEST FORM
        # ====================================================

        st.markdown(
            "### 🧪 Test Control"
        )

        result_options = [
            "Effective",
            "Partially Effective",
            "Ineffective",
            "Not Applicable"
        ]

        default_index = 0

        if existing:

            default_index = result_options.index(
                existing["result"]
            )

        result = st.radio(
            "Test Result",
            result_options,
            index=default_index,
            horizontal=True
        )

        evidence = st.text_area(
            "Evidence Reviewed",
            value=(
                existing["evidence"]
                if existing
                else ""
            ),
            placeholder=(
                "Example: Access Control List, "
                "user access review report..."
            )
        )

        comments = st.text_area(
            "Auditor Comments",
            value=(
                existing["comments"]
                if existing
                else ""
            ),
            placeholder=(
                "Enter testing observations..."
            )
        )

        # ====================================================
        # SAVE
        # ====================================================

        if st.button(
            "💾 SAVE TEST RESULT",
            type="primary"
        ):

            st.session_state.results[
                selected_control
            ] = {

                "result": result,

                "evidence": evidence,

                "comments": comments,

                "tscs": tscs
            }

            st.success(
                f"{selected_control} saved successfully."
            )

            st.rerun()

    # ========================================================
    # RESULTS TABLE
    # ========================================================

    st.divider()

    st.subheader(
        "📋 Centralized Control Results"
    )

    result_rows = []

    for control, result_data in (
        st.session_state.results.items()
    ):

        result_rows.append({

            "Control ID":
                control,

            "Result":
                result_data["result"],

            "Evidence":
                result_data["evidence"],

            "Comments":
                result_data["comments"],

            "TSC Count":
                len(result_data["tscs"])
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
            "No controls have been tested yet."
        )

    # ========================================================
    # GENERATE OUTPUT EXCEL
    # ========================================================

    st.divider()

    st.subheader(
        "📥 Export Audit Results"
    )

    if st.button(
        "Generate Updated Excel"
    ):

        output_df = df.copy()

        output_df[
            "Test Result"
        ] = ""

        output_df[
            "Evidence Reviewed"
        ] = ""

        output_df[
            "Auditor Comments"
        ] = ""

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
                    "Test Result"
                ] = result_data[
                    "result"
                ]

                output_df.at[
                    index,
                    "Evidence Reviewed"
                ] = result_data[
                    "evidence"
                ]

                output_df.at[
                    index,
                    "Auditor Comments"
                ] = result_data[
                    "comments"
                ]

        # ----------------------------------------------------
        # CREATE EXCEL
        # ----------------------------------------------------

        output = BytesIO()

        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:

            output_df.to_excel(
                writer,
                index=False,
                sheet_name=(
                    st.session_state.sheet_name
                    or "SOC2 Results"
                )
            )

            # Centralized results sheet

            if result_rows:

                results_df.to_excel(
                    writer,
                    index=False,
                    sheet_name="Centralized Results"
                )

        output.seek(0)

        st.download_button(
            label="⬇️ Download SOC 2 Results",
            data=output,
            file_name=(
                "SOC2_Control_Testing_Results.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        st.success(
            "Excel file is ready for download."
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
        ### How this system works

        **1. Upload**
        Your existing SOC 2 Excel workbook.

        **2. Identify**
        The system identifies controls appearing
        across multiple TSCs.

        **3. Test once**
        Test each unique control only once.

        **4. Synchronize**
        The result automatically applies to
        every occurrence of that control.

        **5. Export**
        Download the updated SOC 2 workbook.
        """
    )
