import traceback
from google import genai
import asyncio
import functools
import inspect

# Automatically loads the key from the GEMINI_API_KEY environment variable
client = genai.Client()

def get_ai_fix(error: Exception, app_context: dict = None) -> str:
    """
    Sends the exception traceback and application state to Gemini
    and returns an actionable, plain-English fix.
    """
    # 1. Format the raw error traceback nicely
    error_traceback = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    
    # 2. Build a clear, structured prompt for the model
    prompt = f"""
    You are an embedded software engineer debugging a Python network emulator using Google's Bumble BLE stack.
    
    An exception has halted the runtime. Analyze the error trace and context to explain WHAT went wrong and HOW to fix it.
    
    [RAW ERROR TRACE]
    {error_traceback}
    
    [EMULATOR CURRENT CONTEXT]
    {app_context if app_context else 'No context recorded.'}
    
    Provide your response in this clean markdown structure:
    ### 🔍 Root Cause
    (Check what role we are in, are we connected, flow is correct, etc. Explain the failure in simple terms)
    (Explain why this happened in simple terms)
    
    ### 💡 Actionable Fix
    (Give clear code modifications or configuration steps to resolve this)
    """
    
    try:
        # 3. Call the fast, free Gemini 2.5 Flash model
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Could not connect to AI Diagnostic Engine: {str(e)}"

def show_in_separate_window(error_obj, context_dict):
    """
    Fetches Gemini diagnostics and launches a brand new, isolated 
    cmd.exe window to display the results without blocking the main script.
    """
    # 1. Get the AI analysis text
    analysis_text = get_ai_fix(error_obj, context_dict)
    
    # 2. Create a clean display string for the console popup
    content = f"""
============================================================
             🤖 BUMBLE AI DIAGNOSTICS ENGINE               
============================================================

{analysis_text}

============================================================
Press any key to close this diagnostics window . . .
"""

    # 3. Handle OS-specific window spawning (Windows Focus)
    if sys.platform == "win32":
        # Create a temporary batch file that prints the text and pauses
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bat", mode='w', encoding='utf-8') as tf:
            tf.write("@echo off\n")
            tf.write("title Bumble AI Diagnostics Popup\n")
            tf.write("color 0A\n") # Light green text on black background
            # Write out line by line
            for line in content.split('\n'):
                # Escape characters that break batch files echo
                safe_line = line.replace('^', '^^').replace('&', '^&').replace('<', '^<').replace('>', '^>')
                tf.write(f"echo {safe_line}\n")
            tf.write("pause > nul\n")
            tf.write("del \"%~f0\"\n") # Batch file deletes itself when closed
            temp_file_path = tf.name

        # Launch the batch file in a brand-new, detached command prompt window
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "cmd.exe", "/c", temp_file_path],
            creationflags=subprocess.DETACHED_PROCESS
        )
    else:
        # Fallback for Linux/macOS if you test there later
        print("\n--- AI DIAGNOSTICS BACKGROUND OUTPUT ---", content)

def ai_diagnostic_wrapper(context_name: str = "Operation"):
    def decorator(func):
        def run_ai_async_detached(error_obj, context_dict):
            # Grab the running loop to safely toss the heavy window compilation step 
            # into a background thread pool, leaving Bumble completely untouched
            try:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, show_in_separate_window, error_obj, context_dict)
            except RuntimeError:
                # Fallback if no async event loop is active
                show_in_separate_window(error_obj, context_dict)

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_inner(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    context = {"target": context_name, "type": "Async Exception"}
                    run_ai_async_detached(exc, context)
                    raise exc
            return async_inner
        else:
            @functools.wraps(func)
            def sync_inner(*args, **kwargs):
                result = func(*args, **kwargs)
                if "fail" in func.__name__.lower() or "error" in func.__name__.lower():
                    mock_exc = Exception(f"Event failure: {func.__name__}")
                    context = {"target": context_name, "callback_args": str(args)}
                    run_ai_async_detached(mock_exc, context)
                return result
            return sync_inner
    return decorator