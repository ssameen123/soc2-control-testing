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
    "Centralized control testing — test each control once "
    "and automatically synchronize results across all TSCs."
)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("📁 Upload SOC 2 Workbook")

    uploaded_file = st.file_uploader(
        "Upload Excel file",
        type=["xlsx", "xls"]
    )

# ============================================================
# UPLOAD FILE
# ============================================================

if uploaded_file:

    try:

        file_bytes = uploaded_file.read()

        excel = pd.ExcelFile(
            BytesIO(file_bytes)
        )

        st.sidebar.success(
            "Workbook loaded."
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
            f"Unable to read Excel: {e}"
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

    st.header("⚙️ Column Configuration")

    columns = list(df.columns)

    c1, c2 = st.columns(2)

    with c1:

        trust_id_column = st.selectbox(
            "Trust ID column",
            columns
        )

    with c2:

        control_column = st.selectbox(
            "Controls Description column",
            columns
        )

    c3, c4 = st.columns(2)

    with c3:

        tsc_description_column = st.selectbox(
            "TSC Description column",
            columns
        )

    with c4:

        existing_test_column = st.selectbox(
            "Existing Auditor Test column",
            columns
        )

    # ========================================================
    # CLEAN DATA
    # ========================================================

    for column in [
        trust_id_column,
        control_column,
        tsc_description_column,
        existing_test_column
    ]:

        df[column] = (
            df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    # ========================================================
    # TRUST SERVICES CRITERIA
    # ========================================================

    st.divider()

    st.header("🏷️ Trust Services Criteria")

    selected_category = st.radio(
        "Select criteria",
        [
            "All",
            "CC",
            "A",
            "C",
            "P",
            "PI"
        ],
        horizontal=True
    )

    # ========================================================
    # FILTER CATEGORY
    # ========================================================

    if selected_category == "All":

        working_df = df.copy()

    else:

        # Extract category from Trust ID.
        #
        # Example:
        # CC6.1 -> CC
        # A1.1  -> A
        # C1.1  -> C
        # P1.1  -> P
        # PI1.1 -> PI

        def get_category(value):

            value = str(value).upper().strip()

            if value.startswith("PI"):
                return "PI"

            if value.startswith("CC"):
                return "CC"

            if value.startswith("A"):
                return "A"

            if value.startswith("C"):
                return "C"

            if value.startswith("P"):
                return "P"

            return ""

        working_df = df[
            df[trust_id_column]
            .apply(get_category)
            == selected_category
        ].copy()

    # ========================================================
    # DASHBOARD
    # ========================================================

    st.divider()

    # Unique controls

    unique_control_series = (
        working_df[control_column]
        .replace("", pd.NA)
        .dropna()
    )

    unique_controls = (
        unique_control_series
        .drop_duplicates()
        .tolist()
    )

    total_controls = len(
        unique_controls
    )

    tested_controls = len(
        [
            x
            for x in st.session_state.results
            if x in unique_controls
        ]
    )

    remaining_controls = (
        total_controls -
        tested_controls
    )

    exceptions = len(
        [
            x
            for x in st.session_state.results.values()
            if x.get("result")
            == "Exceptions Noted"
        ]
    )

    st.header("📊 Dashboard")

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
        "Exceptions",
        exceptions
    )

    # ========================================================
    # CONTROL TESTING REGISTER
    # ========================================================

    st.divider()

    st.header(
        "🧪 Control Testing Register"
    )

    st.write(
        "Each control appears only once. "
        "Enter the auditor test and result directly "
        "against the control."
    )

    # ========================================================
    # SEARCH
    # ========================================================

    search = st.text_input(
        "🔎 Search controls",
        placeholder="Search control description..."
    )

    if search:

        display_controls = [
            x
            for x in unique_controls
            if search.lower() in x.lower()
        ]

    else:

        display_controls = unique_controls

    # ========================================================
    # CREATE TESTING TABLE
    # ========================================================

    testing_rows = []

    for control in display_controls:

        # All rows belonging to this control

        control_rows = working_df[
            working_df[control_column]
            == control
        ]

        # ----------------------------------------------------
        # Trust IDs
        # ----------------------------------------------------

        trust_ids = (
            control_rows[
                trust_id_column
            ]
            .drop_duplicates()
            .tolist()
        )

        # ----------------------------------------------------
        # TSC descriptions
        # ----------------------------------------------------

        tsc_descriptions = (
            control_rows[
                tsc_description_column
            ]
            .drop_duplicates()
            .tolist()
        )

        # ----------------------------------------------------
        # Existing test
        # ----------------------------------------------------

        existing_tests = (
            control_rows[
                existing_test_column
            ]
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .tolist()
        )

        # ----------------------------------------------------
        # Previous centralized result
        # ----------------------------------------------------

        saved = st.session_state.results.get(
            control,
            {}
        )

        if saved:

            auditor_test = saved.get(
                "auditor_test",
                ""
            )

            result = saved.get(
                "result",
                "Not Tested"
            )

        elif existing_tests:

            auditor_test = existing_tests[0]

            result = "Not Tested"

        else:

            auditor_test = ""

            result = "Not Tested"

        # ----------------------------------------------------
        # Build row
        # ----------------------------------------------------

        testing_rows.append({

            "Control Description":
                control,

            "Trust IDs":
                ", ".join(
                    trust_ids
                ),

            "TSC Description":
                " | ".join(
                    tsc_descriptions
                ),

            "Tests Performed by The Auditor":
                auditor_test,

            "Results":
                result
        })

    # ========================================================
    # TESTING DATAFRAME
    # ========================================================

    testing_df = pd.DataFrame(
        testing_rows
    )

    # ========================================================
    # DISPLAY TABLE
    # ========================================================

    if len(testing_df) > 0:

        edited_df = st.data_editor(

            testing_df,

            use_container_width=True,

            hide_index=True,

            num_rows="fixed",

            column_config={

                "Control Description":
                    st.column_config.TextColumn(
                        "Controls Description",
                        disabled=True,
                        width="large"
                    ),

                "Trust IDs":
                    st.column_config.TextColumn(
                        "Trust ID(s)",
                        disabled=True,
                        width="medium"
                    ),

                "TSC Description":
                    st.column_config.TextColumn(
                        "TSC Description",
                        disabled=True,
                        width="large"
                    ),

                "Tests Performed by The Auditor":
                    st.column_config.TextColumn(
                        "Tests Performed by The Auditor",
                        width="large"
                    ),

                "Results":
                    st.column_config.SelectboxColumn(

                        "Results",

                        options=[
                            "Not Tested",
                            "No Exceptions Noted",
                            "Exceptions Noted",
                            "Not Applicable",
                            "Unable to Test"
                        ],

                        width="medium"
                    )
            },

            key="control_testing_editor"
        )

        # ====================================================
        # SAVE ALL TESTS
        # ====================================================

        st.divider()

        if st.button(
            "💾 SAVE ALL CONTROL TESTS",
            type="primary",
            use_container_width=True
        ):

            for _, row in edited_df.iterrows():

                control = (
                    row[
                        "Control Description"
                    ]
                )

                st.session_state.results[
                    control
                ] = {

                    "auditor_test":
                        row[
                            "Tests Performed by The Auditor"
                        ],

                    "result":
                        row[
                            "Results"
                        ],

                    "trust_ids":
                        row[
                            "Trust IDs"
                        ],

                    "tsc_description":
                        row[
                            "TSC Description"
                        ]
                }

            st.success(
                "All control testing results saved."
            )

            st.rerun()

    else:

        st.warning(
            "No controls found."
        )

    # ========================================================
    # CONTROL TESTING SUMMARY
    # ========================================================

    st.divider()

    st.header(
        "📋 Testing Summary"
    )

    summary_rows = []

    for control in unique_controls:

        saved = (
            st.session_state.results.get(
                control
            )
        )

        if saved:

            summary_rows.append({

                "Control":
                    control,

                "Result":
                    saved[
                        "result"
                    ]
            })

    if summary_rows:

        summary_df = pd.DataFrame(
            summary_rows
        )

        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header(
        "📥 Export SOC 2 Audit Excel"
    )

    if st.button(
        "Generate Final Excel",
        type="primary",
        use_container_width=True
    ):

        # ----------------------------------------------------
        # START WITH ORIGINAL DATA
        # ----------------------------------------------------

        output_df = df.copy()

        # ----------------------------------------------------
        # CREATE REQUIRED OUTPUT COLUMNS
        # ----------------------------------------------------

        output_df["Trust ID"] = (
            output_df[
                trust_id_column
            ]
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
        ] = ""

        output_df["Results"] = ""

        # ----------------------------------------------------
        # APPLY CENTRALIZED TESTING
        # ----------------------------------------------------

        for index, row in output_df.iterrows():

            control = (
                row[
                    control_column
                ]
            )

            saved = (
                st.session_state.results.get(
                    control
                )
            )

            if saved:

                output_df.at[
                    index,
                    "Tests Performed by The Auditor"
                ] = saved[
                    "auditor_test"
                ]

                output_df.at[
                    index,
                    "Results"
                ] = saved[
                    "result"
                ]

        # ----------------------------------------------------
        # FINAL COLUMNS
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
        # EXCEL FILE
        # ----------------------------------------------------

        excel_output = BytesIO()

        with pd.ExcelWriter(
            excel_output,
            engine="openpyxl"
        ) as writer:

            final_df.to_excel(
                writer,
                sheet_name="SOC 2 Audit Results",
                index=False
            )

            # Unique control register

            control_register = pd.DataFrame(
                [
                    {
                        "Controls Description":
                            control,

                        "Trust IDs":
                            value.get(
                                "trust_ids",
                                ""
                            ),

                        "TSC Description":
                            value.get(
                                "tsc_description",
                                ""
                            ),

                        "Tests Performed by The Auditor":
                            value.get(
                                "auditor_test",
                                ""
                            ),

                        "Results":
                            value.get(
                                "result",
                                ""
                            )
                    }

                    for control, value
                    in st.session_state.results.items()
                ]
            )

            control_register.to_excel(
                writer,
                sheet_name="Control Testing Register",
                index=False
            )

        excel_output.seek(0)

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        st.download_button(

            label="⬇️ Download Final SOC 2 Excel",

            data=excel_output,

            file_name=
                "SOC2_Audit_Results.xlsx",

            mime=
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet",

            use_container_width=True
        )

        st.success(
            "Final SOC 2 Excel is ready."
        )

else:

    # ========================================================
    # WELCOME SCREEN
    # ========================================================

    st.info(
        "👈 Upload your SOC 2 Excel workbook "
        "from the sidebar."
    )

    st.markdown(
        """
        ## 🔐 SOC 2 Control Testing System

        ### Features

        **CC / A / C / P / PI selection**

        **One occurrence of each control in the testing register**

        **Control description shown side-by-side with testing**

        **Auditor test procedure editable directly in the table**

        **Result selectable directly in the table**

        **One test automatically synchronized to every occurrence**

        **Final SOC 2 Excel report generated automatically**
        """
    )
