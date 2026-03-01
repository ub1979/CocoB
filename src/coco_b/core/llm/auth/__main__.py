# =============================================================================
'''
    File Name : __main__.py
    
    Description : Entry point for running the auth module directly.
                  Allows execution via: python -m core.llm.auth
                  This enables the OAuth authentication CLI to be invoked
                  as a module without explicitly calling the cli.py file.
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================

from .cli import main

# =============================================================================
# Entry Point
# =============================================================================

# ==================================
if __name__ == "__main__":
    main()


# =============================================================================
# End of File - mr_bot OAuth Module Entry Point
# =============================================================================
