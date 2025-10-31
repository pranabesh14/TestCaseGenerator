
import streamlit as st
import os
import re
import time
import json
from pathlib import Path
from datetime import datetime
from llm_handler import LLMHandler
from code_parser import CodeParser
from test_generator import TestGenerator
from git_handler import GitHandler
from csv_handler import CSVHandler
from rag_system import RAGSystem
from security import SecurityManager
from logger import get_app_logger, TestGenerationLogger

# ---- Logger -------------------------------------------------------------------
logger = get_app_logger("streamlit_app")
test_logger = TestGenerationLogger()
logger.info("=" * 60)
logger.info("Test Case Generator – Unified Chat UI (full features)")
logger.info("=" * 60)

# ---- Page config ---------------------------------------------------------------
st.set_page_config(
    page_title="AI Test Case Generator",
    page_icon="Test",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Session state -------------------------------------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}
if "previous_code" not in st.session_state:
    st.session_state.previous_code = {}
if "rag_system" not in st.session_state:
    st.session_state.rag_system = RAGSystem()
if "llm_handler" not in st.session_state:
    st.session_state.llm_handler = LLMHandler()
if "security_manager" not in st.session_state:
    st.session_state.security_manager = SecurityManager()
if "generated_tests" not in st.session_state:
    st.session_state.generated_tests = {}
if "last_repo_info" not in st.session_state:
    st.session_state.last_repo_info = {}
if "pending_git" not in st.session_state:
    st.session_state.pending_git = None

# # ---- Helper: chat history -------------------------------------------------------
# def save_chat_history():
#     history_dir = Path("chat_history")
#     history_dir.mkdir(exist_ok=True)
#     ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#     fn = history_dir / f"chat_{ts}.json"
#     with open(fn, "w") as f:
#         json.dump(st.session_state.chat_history, f, indent=2)
#     return fn




def generate_chat_name(message: str) -> str:
    """Generate a chat name from the first few words of a message"""
    # Clean the message
    words = message.strip().split()
    
    # Take the first 5 words, and add "..." if there are more than 5 words
    name_words = words[:5]
    name = ' '.join(name_words)
    if len(words) > 5:
        name += "..."
    
    # Remove special characters (keep alphanumeric and underscores)
    name = ''.join(c if c.isalnum() or c == ' ' else '_' for c in name)
    
    # Limit length to 50 characters
    name = name[:50]
    
    # Return the generated name or "chat" if empty
    return name if name else "chat"




def has_context() -> bool:
    """Check if there's any context available (files, repo, or test results)"""
    # Check for uploaded files
    if st.session_state.uploaded_files:
        return True
    
    # Check for repository
    if st.session_state.current_repo_path:
        return True
    
    # Check for test results in chat history
    for message in st.session_state.chat_history:
        if message.get("role") == "assistant" and "test_results" in message:
            return True
    
    # Check if RAG system has documents
    if st.session_state.rag_system.code_documents:
        return True
    
    return False

def auto_save_chat():
    """Auto-save chat after significant interactions"""
    if st.session_state.chat_history and len(st.session_state.chat_history) >= 2:
        # Only auto-save if there's meaningful content
        save_chat_history()

def save_chat_history():
    """Save chat history to file with meaningful name"""
    if not st.session_state.chat_history:
        return None
    
    history_dir = Path("chat_history")
    history_dir.mkdir(exist_ok=True)
    
    # Get first user message for naming
    first_message = None
    for msg in st.session_state.chat_history:
        if msg['role'] == 'user':
            first_message = msg['content']
            break
    
    if first_message:
        chat_name = generate_chat_name(first_message)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = history_dir / f"{chat_name}_{timestamp}.json"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = history_dir / f"chat_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(st.session_state.chat_history, f, indent=2)
    
    return filename

def load_chat_history(filename):
    """Load chat history from file"""
    with open(filename, 'r') as f:
        return json.load(f)

# ---- Helper: change detection ---------------------------------------------------
def detect_code_changes(file_name, current_code):
    if file_name in st.session_state.previous_code:
        prev = st.session_state.previous_code[file_name]
        if prev != current_code:
            prev_lines = set(prev.split("\n"))
            cur_lines = set(current_code.split("\n"))
            added = cur_lines - prev_lines
            removed = prev_lines - cur_lines
            return {
                "changed": True,
                "added_lines": len(added),
                "removed_lines": len(removed),
                "added": list(added)[:5],
                "removed": list(removed)[:5],
            }
    return {"changed": False}

# ---- Helper: test display -------------------------------------------------------
def display_professional_test(test, index):
    test_id = test.get("test_case_id", test.get("name", f"TC-{index:03d}"))
    with st.container():
        st.markdown(f"### {test_id}")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**Description:** {test.get('description', 'N/A')}")
        with col2:
            pri = "High" if "Functional" in test.get("type", "") else "Medium"
            st.markdown(f"**Priority:** {pri}")
        st.markdown("**Target:** " + test.get("target", "N/A"))
        if test.get("file"):
            st.markdown("**File:** " + test.get("file", "N/A"))

        st.markdown("#### Steps")
        steps = test.get("steps", "N/A")
        if steps != "N/A":
            for s in steps.split("\n"):
                if s.strip():
                    st.markdown(f"- {s.strip()}")
        else:
            st.markdown("_No steps_")

        st.markdown("#### Expected Result")
        st.info(test.get("expected_result", "N/A"))
        st.divider()


def display_code_test(test, index):
    name = test.get("name", f"Test {index}")
    code = test.get("code", "No code")
    desc = test.get("description", "")
    file = test.get("file", "N/A")
    chunk = test.get("chunk_name", "N/A")
    st.markdown(f"**Test {index}:** {name}")
    st.caption(f"{file} | Chunk: {chunk}")
    if desc:
        st.caption(desc)
    st.code(code, language="python")

# ---- Sidebar (unchanged) --------------------------------------------------------
def display_sidebar():
    with st.sidebar:
        st.title("Test Generator")
        st.info("NEW: Functional tests in professional format!")

        st.subheader("Test Case Types")
        test_types = st.multiselect(
            "Select test case types:",
            ["Unit Test", "Functional Test"],
            default=["Unit Test", "Functional Test"],
        )

    
        st.divider()
        
        # Chat history management
        st.subheader("📜 Chat History")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🆕 New", use_container_width=True, help="Start a new chat"):
                # Auto-save current chat before clearing
                if st.session_state.chat_history:
                    save_chat_history()
                st.session_state.chat_history = []
                st.session_state.uploaded_files = {}
                st.session_state.current_repo_path = None
                st.success("New chat started!")
                st.rerun()
        
        with col2:
            if st.button("💾 Save", use_container_width=True, help="Save current chat"):
                if st.session_state.chat_history:
                    filename = save_chat_history()
                    if filename:
                        st.success(f"Saved!")
                else:
                    st.warning("No chat to save")
        
        with col3:
            if st.button("🗑️ Clear", use_container_width=True, help="Clear without saving"):
                st.session_state.chat_history = []
                st.session_state.uploaded_files = {}
                st.session_state.current_repo_path = None
                st.rerun()
        
        st.divider()
        
        # Display saved chats
        history_dir = Path("chat_history")
        if history_dir.exists():
            chat_files = sorted(history_dir.glob("*.json"), reverse=True)
            if chat_files:
                st.write("**Recent Chats:**")
                for chat_file in chat_files[:10]:
                    # Extract readable name from filename
                    name = chat_file.stem
                    # Remove timestamp if present
                    parts = name.split('_')
                    if len(parts) > 1 and parts[-1].isdigit():
                        display_name = '_'.join(parts[:-2])  # Remove date and time
                    else:
                        display_name = name
                    
                    # Limit display name length
                    if len(display_name) > 30:
                        display_name = display_name[:30] + "..."
                    
                    if st.button(f"📄 {display_name}", key=chat_file.name, use_container_width=True):
                        st.session_state.chat_history = load_chat_history(chat_file)
                        st.rerun()
        return test_types

# ---- Unified Chat UI ------------------------------------------------------------
def display_chat():
    st.subheader("AI Test Case Generator")

    # ----- Input row (chat + attach) -----
    # col_chat = st.column
    # with col_chat:
    #     user_input = st.chat_input("Ask, paste Git URL, or type 'generate'...")
    #     uploaded_files = st.file_uploader(
    #         "Attach",
    #         accept_multiple_files=True,
    #         type=[
    #             "py","js","java","cpp","c","cs","go","rb","php","swift","kt","ts","rs"
    #         ],
    #         key="chat_uploader",
    #         # label_visibility="collapsed",
    #     )
    # import streamlit as st

    # Create a container or column for both chat input and file uploader
    with st.container():  # This ensures both elements are inside the same section
        user_input = st.chat_input("Ask, paste Git URL, or type 'generate'...")

        uploaded_files = st.file_uploader(
            "Attach",
            accept_multiple_files=True,
            type=[
                "py", "js", "java", "cpp", "c", "cs", "go", "rb", "php", "swift", "kt", "ts", "rs"
            ],
            key="chat_uploader",
            label_visibility="collapsed",  # Keeps the file uploader label hidden for a cleaner look
        )

    # Optional: display uploaded files below the uploader
    if uploaded_files:
        st.write(f"Uploaded files: {[file.name for file in uploaded_files]}")


   

 
    # ----- Show history -----
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ----- Process uploaded files -----
    if uploaded_files:
        names = []
        for uf in uploaded_files:
            try:
                txt = uf.read().decode("utf-8")
                changes = detect_code_changes(uf.name, txt)
                st.session_state.uploaded_files[uf.name] = txt
                st.session_state.previous_code[uf.name] = txt

                if changes["changed"]:
                    st.warning(f"Changes in **{uf.name}**")
                    with st.expander("View diff"):
                        st.write(f"+{changes['added_lines']}  -{changes['removed_lines']} lines")
                        if changes["added"]:
                            st.write("**Added:** " + ", ".join(changes["added"]))
                        if changes["removed"]:
                            st.write("**Removed:** " + ", ".join(changes["removed"]))

                lines = len(txt.splitlines())
                with st.expander(f"{uf.name} ({lines} lines)"):
                    st.code(txt[:1000], language="python")
                    if len(txt) > 1000:
                        st.caption(f"... ({len(txt)} chars total)")

                names.append(f"`{uf.name}`")
            except Exception as e:
                st.error(f"Error reading {uf.name}: {e}")

        if names:
            msg = f"Uploaded: {', '.join(names)}"
            st.session_state.chat_history.append(
                {"role": "user", "content": msg, "timestamp": datetime.now().isoformat()}
            )
            with st.chat_message("user"):
                st.markdown(msg)

    # ----- Process text input -----
    if user_input:
        sanitized = st.session_state.security_manager.sanitize_input(user_input)
        st.session_state.chat_history.append(
            {"role": "user", "content": sanitized, "timestamp": datetime.now().isoformat()}
        )
        with st.chat_message("user"):
            st.markdown(sanitized)

        # ---- Git URL detection ----
        git_pat = re.compile(r"(https?://|git@)[\w\.\-@:/~]+?\.git", re.IGNORECASE)
        m = git_pat.search(sanitized)
        if m:
            url = m.group(0).strip()
            st.session_state.pending_git = {"url": url, "stage": "ask_branch"}
            bot = (
                f"Found repository: **{url}**\n"
                "Please tell me the **branch** (default: `main`):"
            )
            st.session_state.chat_history.append(
                {"role": "assistant", "content": bot, "timestamp": datetime.now().isoformat()}
            )
            with st.chat_message("assistant"):
                st.markdown(bot)
            return

        # ---- Generate from uploaded files (keyword) ----
        if "generate" in sanitized.lower() and st.session_state.uploaded_files:
            with st.chat_message("assistant"):
                with st.spinner("Generating tests from uploaded files..."):
                    start = time.time()
                    parser = CodeParser()
                    parsed = {
                        n: parser.parse_code(c, n)
                        for n, c in st.session_state.uploaded_files.items()
                    }
                    st.session_state.rag_system.add_code_documents(parsed)

                    gen = TestGenerator(st.session_state.llm_handler, st.session_state.rag_system)
                    tests = gen.generate_tests(parsed, test_types, module_level=True)
                    st.session_state.generated_tests = tests
                    st.session_state.rag_system.add_test_cases(tests, session_id="current")

                    total = sum(len(v) for v in tests.values())
                    elapsed = time.time() - start

                    st.success(f"Generated **{total}** tests in {elapsed:.2f}s")

                    # ---- Metrics ----
                    c1, c2, c3 = st.columns(3)
                    with c1: st.metric("Total", total)
                    with c2: st.metric("Unit", len(tests.get("Unit Test", [])))
                    # with c3: st.metric("Regression", len(tests.get("Regression Test", [])))
                    with c3: st.metric("Functional", len(tests.get("Functional Test", [])))

                    # ---- Download ----
                    csv_h = CSVHandler()
                    csv_file = csv_h.generate_csv(tests)
                    report_file = csv_h.generate_professional_test_report(tests)
                    d1, d2 = st.columns(2)
                    with d1:
                        with open(csv_file, "rb") as f:
                            st.download_button(
                                "CSV", data=f,
                                file_name=f"tests_{datetime.now():%Y%m%d_%H%M%S}.csv",
                                mime="text/csv",
                            )
                    with d2:
                        with open(report_file, "rb") as f:
                            st.download_button(
                                "Report", data=f,
                                file_name=f"report_{datetime.now():%Y%m%d_%H%M%S}.txt",
                                mime="text/plain",
                            )

                    # ---- Show tests (first 10 per type) ----
                    for ttype in test_types:
                        lst = tests.get(ttype, [])
                        if lst:
                            with st.expander(f"{ttype}s ({len(lst)})", expanded=True):
                                for i, t in enumerate(lst[:10], 1):
                                    if t.get("format") == "professional":
                                        display_professional_test(t, i)
                                    else:
                                        display_code_test(t, i)
                                if len(lst) > 10:
                                    st.info(f"... and {len(lst)-10} more (download CSV)")

            return

        # ---- Normal LLM chat ----
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                ctx = st.session_state.rag_system.get_relevant_context(sanitized)
                reply = st.session_state.llm_handler.generate_chat_response(
                    sanitized, ctx, st.session_state.chat_history
                )
                st.markdown(reply)
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": reply, "timestamp": datetime.now().isoformat()}
                )

    # ---- Pending Git flow (branch → clone → generate) ----
    if st.session_state.pending_git and user_input:
        pend = st.session_state.pending_git
        if pend["stage"] == "ask_branch":
            branch = user_input.strip() or "main"
            pend["branch"] = branch
            pend["stage"] = "processing"

            with st.chat_message("assistant"):
                st.markdown(f"Cloning **{branch}** …")

            with st.spinner("Cloning & analysing repository…"):
                try:
                    gh = GitHandler()
                    repo_path, change_info = gh.clone_or_pull_repository(
                        pend["url"], branch, depth=1
                    )

                    # ---- No changes → reuse previous CSV ----
                    if not change_info["has_changes"] and not change_info["is_new_repo"]:
                        st.info("No new changes in the repository. No new test cases generated.")
                        prev_csv = gh.get_previous_test_file(pend["url"])
                        if prev_csv:
                            csv_h = CSVHandler()
                            report = csv_h.generate_no_changes_report(
                                prev_csv,
                                gh._sanitize_repo_name(pend["url"]),
                                gh.get_commit_info(repo_path),
                            )
                            st.success("No code changes – using previous test suite")
                            d1, d2 = st.columns(2)
                            with d1:
                                with open(prev_csv, "rb") as f:
                                    st.download_button(
                                        "Previous CSV", data=f,
                                        file_name=prev_csv.name, mime="text/csv"
                                    )
                            with d2:
                                with open(report, "rb") as f:
                                    st.download_button(
                                        "No-Changes Report", data=f,
                                        file_name=report.name, mime="text/plain"
                                    )
                            st.session_state.pending_git = None
                            return

                    # ---- Parse code (changed files or all) ----
                    if change_info.get("has_changes"):
                        code_files = gh.get_changed_code_files(
                            repo_path, change_info.get("changed_files", [])
                        )
                        st.info(f"Processing **{len(code_files)}** changed files")
                    else:
                        code_files = gh.get_code_files(repo_path)

                    parser = CodeParser()
                    parsed = {}
                    prog = st.progress(0)
                    for i, fp in enumerate(code_files):
                        try:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                                parsed[fp.name] = parser.parse_code(f.read(), fp.name)
                        except Exception as e:
                            logger.warning(f"Parse error {fp}: {e}")
                        prog.progress((i + 1) / len(code_files))
                    prog.empty()

                    if not parsed:
                        st.error("No code files could be parsed.")
                        st.session_state.pending_git = None
                        return

                    st.session_state.rag_system.add_code_documents(parsed)

                    # ---- Generate tests ----
                    gen = TestGenerator(st.session_state.llm_handler, st.session_state.rag_system)
                    tests = gen.generate_tests(parsed, test_types, module_level=True)
                    st.session_state.generated_tests = tests
                    st.session_state.rag_system.add_test_cases(tests, session_id="current")

                    total = sum(len(v) for v in tests.values())
                    st.success(f"Generated **{total}** test cases")

                    # ---- CSV handling (append or new) ----
                    csv_h = CSVHandler()
                    prev_csv = gh.get_previous_test_file(pend["url"])
                    if prev_csv and change_info.get("has_changes"):
                        csv_file = csv_h.append_to_previous_csv(prev_csv, tests, change_info)
                        st.info("Appended new tests to previous suite")
                    else:
                        csv_file = csv_h.generate_csv_with_repo_name(
                            tests, gh._sanitize_repo_name(pend["url"]), change_info
                        )

                    report_file = csv_h.generate_professional_test_report(tests)

                    d1, d2 = st.columns(2)
                    with d1:
                        with open(csv_file, "rb") as f:
                            st.download_button(
                                "CSV", data=f,
                                file_name=f"tests_{datetime.now():%Y%m%d_%H%M%S}.csv",
                                mime="text/csv",
                            )
                    with d2:
                        with open(report_file, "rb") as f:
                            st.download_button(
                                "Report", data=f,
                                file_name=f"report_{datetime.now():%Y%m%d_%H%M%S}.txt",
                                mime="text/plain",
                            )

                    # ---- Repo stats ----
                    with st.expander("Repository Statistics"):
                        struct = gh.get_repo_structure(repo_path)
                        c1, c2, c3 = st.columns(3)
                        with c1: st.metric("Total Files", struct["total_files"])
                        with c2: st.metric("Code Files", struct["code_files"])
                        with c3: st.metric("Languages", len(struct["languages"]))
                        if struct["languages"]:
                            st.write(", ".join(struct["languages"]))

                    # ---- Show first 10 tests per type ----
                    for ttype in test_types:
                        lst = tests.get(ttype, [])
                        if lst:
                            with st.expander(f"{ttype}s ({len(lst)})", expanded=False):
                                for i, t in enumerate(lst[:10], 1):
                                    if t.get("format") == "professional":
                                        display_professional_test(t, i)
                                    else:
                                        display_code_test(t, i)
                                if len(lst) > 10:
                                    st.info(f"... and {len(lst)-10} more (download CSV)")

                    st.session_state.pending_git = None

                except Exception as e:
                    st.error(f"Git processing failed: {e}")
                    with st.expander("Details"):
                        st.code(str(e))
                    st.session_state.pending_git = None

# ---- Main -----------------------------------------------------------------------
def main():
    global test_types
    test_types = display_sidebar()
    display_chat()

if __name__ == "__main__":
    main()