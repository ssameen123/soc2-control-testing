import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="SOC 2 Control Testing System",
    page_icon="🔐",
    layout="wide"
)

# ============================================================
# AUTOSAVE / RECOVERY SETUP
# ============================================================
#
# Everything the auditor does is written to disk immediately:
#
#   soc2_autosave/
#       last_session.json               -> which workbook/sheet was open last
#       <workbook_id>/workbook.xlsx     -> copy of the uploaded workbook
#       <workbook_id>/progress_<sheet>.json      -> testing results + settings
#       <workbook_id>/progress_<sheet>.bak.json  -> previous version (fallback)
#
# If the browser is closed, the tab is refreshed, or the app crashes,
# the last session is restored automatically on the next start.

AUTOSAVE_DIR = Path(__file__).resolve().parent / "soc2_autosave"
AUTOSAVE_DIR.mkdir(exist_ok=True)
LAST_SESSION_FILE = AUTOSAVE_DIR / "last_session.json"

COLUMN_KEYS = [
    "col_trust_id",
    "col_control",
    "col_tsc_description",
    "col_existing_test",
]

RESULT_OPTIONS = [
    "Not Tested",
    "No Exceptions Noted",
    "Exceptions Noted",
    "Not Applicable",
    "Unable to Test"
]


def atomic_write_json(path: Path, payload: dict):
    """Write JSON so that a crash mid-write never corrupts the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def clean_value(value):
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)


def workbook_dir(workbook_id: str) -> Path:
    return AUTOSAVE_DIR / workbook_id


def progress_paths(workbook_id: str, sheet_name: str):
    sheet_hash = hashlib.md5(sheet_name.encode("utf-8")).hexdigest()[:10]
    folder = workbook_dir(workbook_id)
    return (
        folder / f"progress_{sheet_hash}.json",
        folder / f"progress_{sheet_hash}.bak.json",
    )


def load_progress(workbook_id: str, sheet_name: str) -> dict:
    main, backup = progress_paths(workbook_id, sheet_name)
    return read_json(main) or read_json(backup) or {}


def save_progress():
    """Persist results + column settings for the open worksheet."""
    ss = st.session_state

    if not ss.get("workbook_id") or not ss.get("sheet_name"):
        return

    saved_at = datetime.now().isoformat(timespec="seconds")

    payload = {
        "version": 1,
        "saved_at": saved_at,
        "workbook_id": ss.workbook_id,
        "workbook_name": ss.workbook_name,
        "sheet_name": ss.sheet_name,
        "columns": {k: ss.get(k) for k in COLUMN_KEYS if ss.get(k)},
        "results": ss.results,
    }

    main, backup = progress_paths(ss.workbook_id, ss.sheet_name)

    if main.exists():
        shutil.copy2(main, backup)

    atomic_write_json(main, payload)

    atomic_write_json(LAST_SESSION_FILE, {
        "workbook_id": ss.workbook_id,
        "workbook_name": ss.workbook_name,
        "workbook_file": ss.workbook_file,
        "sheet_name": ss.sheet_name,
        "saved_at": saved_at,
    })

    ss.last_saved = saved_at


def store_workbook(file_bytes: bytes, file_name: str):
    """Keep a copy of the uploaded workbook so it can be reopened later."""
    workbook_id = hashlib.sha256(file_bytes).hexdigest()[:16]
    suffix = Path(file_name).suffix or ".xlsx"
    path = workbook_dir(workbook_id) / f"workbook{suffix}"

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes)

    return workbook_id, str(path)


def open_worksheet(file_bytes, workbook_name, workbook_id, workbook_file, sheet_name):
    """Load a worksheet and any progress previously saved for it."""
    ss = st.session_state

    df = pd.read_excel(BytesIO(file_bytes), sheet_name=sheet_name)
    df.columns = [str(c) for c in df.columns]

    ss.data = df
    ss.workbook_id = workbook_id
    ss.workbook_name = workbook_name
    ss.workbook_file = workbook_file
    ss.sheet_name = sheet_name

    saved = load_progress(workbook_id, sheet_name)

    ss.results = saved.get("results", {})

    saved_columns = saved.get("columns", {})

    for key in COLUMN_KEYS:
        value = saved_columns.get(key)
        if value in df.columns:
            ss[key] = value
        else:
            ss.pop(key, None)

    ss.last_saved = saved.get("saved_at")

    save_progress()

    return bool(saved.get("results"))


def on_editor_change(editor_key, base_rows):
    """Autosave every cell edit the moment it happens."""
    ss = st.session_state
    editor_state = ss.get(editor_key, {})

    for idx, changes in editor_state.get("edited_rows", {}).items():
        idx = int(idx)
        if idx >= len(base_rows):
            continue

        row = dict(base_rows[idx])
        row.update(changes)

        ss.results[row["Control Description"]] = {
            "auditor_test": clean_value(row["Tests Performed by The Auditor"]),
            "result": clean_value(row["Results"]) or "Not Tested",
            "trust_ids": clean_value(row["Trust IDs"]),
            "tsc_description": clean_value(row["TSC Description"]),
        }

    save_progress()


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "data": None,
    "results": {},
    "sheet_name": "",
    "workbook_id": "",
    "workbook_name": "",
    "workbook_file": "",
    "last_saved": None,
    "restore_checked": False,
    "restore_message": "",
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ============================================================
# AUTOMATIC RECOVERY OF THE LAST SESSION
# ============================================================

if st.session_state.data is None and not st.session_state.restore_checked:

    st.session_state.restore_checked = True

    last = read_json(LAST_SESSION_FILE)

    if last and Path(last.get("workbook_file", "")).exists():

        try:
            open_worksheet(
                Path(last["workbook_file"]).read_bytes(),
                last["workbook_name"],
                last["workbook_id"],
                last["workbook_file"],
                last["sheet_name"],
            )

            st.session_state.restore_message = (
                f"Restored previous session: **{last['workbook_name']}** "
                f"→ *{last['sheet_name']}* "
                f"(last saved {last.get('saved_at', 'unknown')})."
            )

        except Exception as e:
            st.session_state.restore_message = (
                f"Could not restore previous session: {e}"
            )

# ============================================================
# HEADER
# ============================================================

st.title("🔐 SOC 2 Control Testing System")

st.caption(
    "Centralized control testing — test each control once "
    "and automatically synchronize results across all TSCs."
)

if st.session_state.restore_message:
    st.info(st.session_state.restore_message)
    st.session_state.restore_message = ""

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

        file_bytes = uploaded_file.getvalue()

        excel = pd.ExcelFile(BytesIO(file_bytes))

        st.sidebar.success("Workbook loaded.")

        selected_sheet = st.sidebar.selectbox(
            "Select worksheet",
            excel.sheet_names
        )

        if st.sidebar.button("Load Worksheet", type="primary"):

            workbook_id, workbook_file = store_workbook(
                file_bytes,
                uploaded_file.name
            )

            had_progress = open_worksheet(
                file_bytes,
                uploaded_file.name,
                workbook_id,
                workbook_file,
                selected_sheet,
            )

            if had_progress:
                st.session_state.restore_message = (
                    "Saved progress found for this workbook and worksheet "
                    "and has been reloaded."
                )

            st.rerun()

    except Exception as e:

        st.error(f"Unable to read Excel: {e}")

# ============================================================
# SIDEBAR — SAVE STATUS, BACKUP & RESET
# ============================================================

with st.sidebar:

    if st.session_state.data is not None:

        st.divider()

        st.header("💾 Progress")

        st.caption(
            f"Workbook: **{st.session_state.workbook_name}**  \n"
            f"Sheet: **{st.session_state.sheet_name}**"
        )

        if st.session_state.last_saved:
            st.success(f"Autosaved at {st.session_state.last_saved}")

        # Download a backup copy of progress (useful on cloud hosts
        # where the server disk is wiped on restart).

        backup_payload = json.dumps(
            {
                "workbook_name": st.session_state.workbook_name,
                "sheet_name": st.session_state.sheet_name,
                "saved_at": st.session_state.last_saved,
                "results": st.session_state.results,
            },
            indent=2,
            ensure_ascii=False,
        )

        st.download_button(
            "⬇️ Download progress backup",
            data=backup_payload,
            file_name="soc2_progress_backup.json",
            mime="application/json",
            use_container_width=True,
        )

        backup_file = st.file_uploader(
            "Restore from backup (.json)",
            type=["json"],
            key="backup_uploader",
        )

        if backup_file and st.button("Restore backup", use_container_width=True):
            try:
                restored = json.loads(backup_file.getvalue().decode("utf-8"))
                st.session_state.results.update(restored.get("results", {}))
                save_progress()
                st.session_state.restore_message = "Backup restored."
                st.rerun()
            except Exception as e:
                st.error(f"Invalid backup file: {e}")

        with st.expander("⚠️ Reset progress"):

            confirm = st.checkbox(
                "I understand this deletes all saved results for this sheet."
            )

            if st.button("Delete saved progress", disabled=not confirm):
                st.session_state.results = {}
                save_progress()
                st.rerun()

# ============================================================
# MAIN APPLICATION
# ============================================================

if st.session_state.data is not None:

    df = st.session_state.data.copy()

    st.divider()

    # ========================================================
    # COLUMN CONFIGURATION (remembered between sessions)
    # ========================================================

    st.header("⚙️ Column Configuration")

    columns = list(df.columns)

    for key in COLUMN_KEYS:
        if st.session_state.get(key) not in columns:
            st.session_state.pop(key, None)

    c1, c2 = st.columns(2)

    with c1:
        trust_id_column = st.selectbox(
            "Trust ID column",
            columns,
            key="col_trust_id",
            on_change=save_progress,
        )

    with c2:
        control_column = st.selectbox(
            "Controls Description column",
            columns,
            key="col_control",
            on_change=save_progress,
        )

    c3, c4 = st.columns(2)

    with c3:
        tsc_description_column = st.selectbox(
            "TSC Description column",
            columns,
            key="col_tsc_description",
            on_change=save_progress,
        )

    with c4:
        existing_test_column = st.selectbox(
            "Existing Auditor Test column",
            columns,
            key="col_existing_test",
            on_change=save_progress,
        )

    # ========================================================
    # CLEAN DATA
    # ========================================================

    for column in {
        trust_id_column,
        control_column,
        tsc_description_column,
        existing_test_column
    }:
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
        ["All", "CC", "A", "C", "P", "PI"],
        horizontal=True,
        key="selected_category",
    )

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

    if selected_category == "All":
        working_df = df.copy()
    else:
        working_df = df[
            df[trust_id_column].apply(get_category) == selected_category
        ].copy()

    # ========================================================
    # DASHBOARD
    # ========================================================

    st.divider()

    unique_controls = (
        working_df[control_column]
        .replace("", pd.NA)
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    unique_set = set(unique_controls)

    in_scope_results = [
        value
        for control, value in st.session_state.results.items()
        if control in unique_set
    ]

    total_controls = len(unique_controls)

    tested_controls = len([
        x for x in in_scope_results
        if x.get("result") not in ("", "Not Tested")
    ])

    remaining_controls = total_controls - tested_controls

    exceptions = len([
        x for x in in_scope_results
        if x.get("result") == "Exceptions Noted"
    ])

    st.header("📊 Dashboard")

    m1, m2, m3, m4 = st.columns(4)

    m1.metric("Unique Controls", total_controls)
    m2.metric("Tested", tested_controls)
    m3.metric("Remaining", remaining_controls)
    m4.metric("Exceptions", exceptions)

    if total_controls:
        st.progress(tested_controls / total_controls)

    # ========================================================
    # CONTROL TESTING REGISTER
    # ========================================================

    st.divider()

    st.header("🧪 Control Testing Register")

    st.write(
        "Each control appears only once. "
        "Enter the auditor test and result directly against the control. "
        "**Every change is saved automatically.**"
    )

    search = st.text_input(
        "🔎 Search controls",
        placeholder="Search control description...",
        key="search_text",
    )

    if search:
        display_controls = [
            x for x in unique_controls
            if search.lower() in x.lower()
        ]
    else:
        display_controls = unique_controls

    # ========================================================
    # CREATE TESTING TABLE
    # ========================================================

    testing_rows = []

    for control in display_controls:

        control_rows = working_df[working_df[control_column] == control]

        trust_ids = (
            control_rows[trust_id_column]
            .drop_duplicates()
            .tolist()
        )

        tsc_descriptions = (
            control_rows[tsc_description_column]
            .drop_duplicates()
            .tolist()
        )

        existing_tests = (
            control_rows[existing_test_column]
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .tolist()
        )

        saved = st.session_state.results.get(control, {})

        if saved:
            auditor_test = saved.get("auditor_test", "")
            result = saved.get("result", "Not Tested")
        elif existing_tests:
            auditor_test = existing_tests[0]
            result = "Not Tested"
        else:
            auditor_test = ""
            result = "Not Tested"

        testing_rows.append({
            "Control Description": control,
            "Trust IDs": ", ".join(trust_ids),
            "TSC Description": " | ".join(tsc_descriptions),
            "Tests Performed by The Auditor": auditor_test,
            "Results": result,
        })

    testing_df = pd.DataFrame(testing_rows)

    # ========================================================
    # DISPLAY TABLE (autosaves on every edit)
    # ========================================================

    if len(testing_df) > 0:

        # The key changes when the set of visible rows changes
        # (category filter / search), so edits never get applied
        # to the wrong row.

        view_signature = hashlib.md5(
            "\n".join(
                [st.session_state.sheet_name, selected_category]
                + display_controls
            ).encode("utf-8")
        ).hexdigest()[:12]

        editor_key = f"control_testing_editor_{view_signature}"

        edited_df = st.data_editor(
            testing_df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "Control Description": st.column_config.TextColumn(
                    "Controls Description",
                    disabled=True,
                    width="large"
                ),
                "Trust IDs": st.column_config.TextColumn(
                    "Trust ID(s)",
                    disabled=True,
                    width="medium"
                ),
                "TSC Description": st.column_config.TextColumn(
                    "TSC Description",
                    disabled=True,
                    width="large"
                ),
                "Tests Performed by The Auditor": st.column_config.TextColumn(
                    "Tests Performed by The Auditor",
                    width="large"
                ),
                "Results": st.column_config.SelectboxColumn(
                    "Results",
                    options=RESULT_OPTIONS,
                    width="medium"
                ),
            },
            key=editor_key,
            on_change=on_editor_change,
            args=(editor_key, testing_rows),
        )

        # ====================================================
        # MANUAL SAVE (still available, autosave already runs)
        # ====================================================

        st.divider()

        if st.button(
            "💾 SAVE ALL CONTROL TESTS",
            type="primary",
            use_container_width=True
        ):

            for _, row in edited_df.iterrows():
                st.session_state.results[row["Control Description"]] = {
                    "auditor_test": clean_value(row["Tests Performed by The Auditor"]),
                    "result": clean_value(row["Results"]) or "Not Tested",
                    "trust_ids": clean_value(row["Trust IDs"]),
                    "tsc_description": clean_value(row["TSC Description"]),
                }

            save_progress()

            st.toast("All control testing results saved.", icon="✅")

            st.rerun()

    else:

        st.warning("No controls found.")

    # ========================================================
    # CONTROL TESTING SUMMARY
    # ========================================================

    st.divider()

    st.header("📋 Testing Summary")

    summary_rows = [
        {"Control": control, "Result": st.session_state.results[control]["result"]}
        for control in unique_controls
        if control in st.session_state.results
    ]

    if summary_rows:
        st.dataframe(
            pd.DataFrame(summary_rows),
            use_container_width=True,
            hide_index=True
        )

    # ========================================================
    # EXPORT
    # ========================================================

    st.divider()

    st.header("📥 Export SOC 2 Audit Excel")

    if st.button(
        "Generate Final Excel",
        type="primary",
        use_container_width=True
    ):

        output_df = df.copy()

        output_df["Trust ID"] = output_df[trust_id_column]
        output_df["TSC Description"] = output_df[tsc_description_column]
        output_df["Controls Description"] = output_df[control_column]
        output_df["Tests Performed by The Auditor"] = ""
        output_df["Results"] = ""

        for index, row in output_df.iterrows():
            saved = st.session_state.results.get(row[control_column])
            if saved:
                output_df.at[index, "Tests Performed by The Auditor"] = saved["auditor_test"]
                output_df.at[index, "Results"] = saved["result"]

        final_df = output_df[[
            "Trust ID",
            "TSC Description",
            "Controls Description",
            "Tests Performed by The Auditor",
            "Results",
        ]].copy()

        excel_output = BytesIO()

        with pd.ExcelWriter(excel_output, engine="openpyxl") as writer:

            final_df.to_excel(
                writer,
                sheet_name="SOC 2 Audit Results",
                index=False
            )

            control_register = pd.DataFrame([
                {
                    "Controls Description": control,
                    "Trust IDs": value.get("trust_ids", ""),
                    "TSC Description": value.get("tsc_description", ""),
                    "Tests Performed by The Auditor": value.get("auditor_test", ""),
                    "Results": value.get("result", ""),
                }
                for control, value in st.session_state.results.items()
            ])

            control_register.to_excel(
                writer,
                sheet_name="Control Testing Register",
                index=False
            )

        excel_output.seek(0)

        st.download_button(
            label="⬇️ Download Final SOC 2 Excel",
            data=excel_output,
            file_name="SOC2_Audit_Results.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            use_container_width=True
        )

        st.success("Final SOC 2 Excel is ready.")

else:

    # ========================================================
    # WELCOME SCREEN
    # ========================================================

    st.info("👈 Upload your SOC 2 Excel workbook from the sidebar.")

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

        **Automatic saving — progress survives browser closure, refresh or crash**

        **Final SOC 2 Excel report generated automatically**
        """
    )
