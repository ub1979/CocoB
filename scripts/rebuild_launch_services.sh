#!/bin/bash
# This script rebuilds the macOS Launch Services database.
echo "Rebuilding Launch Services database. This may take a moment..."
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user
echo "Database rebuild command issued. Please restart your Mac to ensure changes take effect."
