#!/usr/bin/env python3
"""
    File Name : gradio_ui.py
    
    Description : Modern, Professional Gradio Chat Interface for mr_bot
                  Features a clean, international-standard design with:
                  - Modern glass-morphism aesthetics
                  - Professional color scheme
                  - Smooth animations and transitions
                  - Responsive layout
                  - Accessibility features
                  - Icon integration
                  - Real-time status indicators
    
    Modifying it on 2026-02-07
    
    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
    
    Project : mr_bot - Persistent Memory AI Chatbot
    
    License : Open Source - Safe Open Community Project
    
    Mission : Making AI Useful for Everyone
    
    Contact : Idrak AI Ltd - Building AI Solutions for the Community
"""

import sys
from coco_b import PROJECT_ROOT

import gradio as gr
import asyncio
import os
import subprocess
import requests
from datetime import datetime
from coco_b.core.sessions import SessionManager
from coco_b.core.llm import LLMProviderFactory
from coco_b.core.router import MessageRouter
from coco_b.ui.settings.state import AppState
from coco_b.ui.settings.provider_tab import create_provider_tab
from coco_b.ui.settings.skills_tab import create_skills_tab
from coco_b.ui.chat.handlers import chat_with_bot
import config

from coco_b.ui.settings.provider_tab import check_local_server_status, get_server_start_command

# =============================================================================
# Modern Professional Theme Configuration
# =============================================================================

CUSTOM_CSS = """
/* =============================================================================
   Modern Professional Theme - International Standards
   ============================================================================= */

/* Import Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Root Variables - Professional Color Palette */
:root {
    /* Primary Colors */
    --primary-50: #eff6ff;
    --primary-100: #dbeafe;
    --primary-200: #bfdbfe;
    --primary-300: #93c5fd;
    --primary-400: #60a5fa;
    --primary-500: #3b82f6;
    --primary-600: #2563eb;
    --primary-700: #1d4ed8;
    --primary-800: #1e40af;
    --primary-900: #1e3a8a;
    
    /* Neutral Colors */
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-400: #9ca3af;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;
    
    /* Semantic Colors */
    --success-50: #f0fdf4;
    --success-500: #22c55e;
    --success-600: #16a34a;
    --warning-50: #fffbeb;
    --warning-500: #f59e0b;
    --warning-600: #d97706;
    --error-50: #fef2f2;
    --error-500: #ef4444;
    --error-600: #dc2626;
    
    /* Glass Effect */
    --glass-bg: rgba(255, 255, 255, 0.85);
    --glass-border: rgba(255, 255, 255, 0.3);
    --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    
    /* Spacing */
    --space-1: 0.25rem;
    --space-2: 0.5rem;
    --space-3: 0.75rem;
    --space-4: 1rem;
    --space-5: 1.25rem;
    --space-6: 1.5rem;
    --space-8: 2rem;
    --space-10: 2.5rem;
    --space-12: 3rem;
    
    /* Border Radius */
    --radius-sm: 0.375rem;
    --radius-md: 0.5rem;
    --radius-lg: 0.75rem;
    --radius-xl: 1rem;
    --radius-2xl: 1.5rem;
    --radius-full: 9999px;
}

/* =============================================================================
   Global Styles
   ============================================================================= */
* {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* Main Container */
.main-container {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    min-height: 100vh !important;
    padding: var(--space-6) !important;
}

/* Glass Card Effect */
.glass-card {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius-2xl) !important;
    box-shadow: var(--glass-shadow) !important;
    padding: var(--space-6) !important;
    transition: all 0.3s ease !important;
}

.glass-card:hover {
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15) !important;
    transform: translateY(-2px) !important;
}

/* =============================================================================
   Header Styles
   ============================================================================= */
.header-container {
    text-align: center !important;
    padding: var(--space-8) var(--space-6) !important;
    background: linear-gradient(135deg, var(--primary-600) 0%, var(--primary-800) 100%) !important;
    border-radius: var(--radius-2xl) !important;
    margin-bottom: var(--space-6) !important;
    box-shadow: 0 10px 40px rgba(37, 99, 235, 0.3) !important;
}

.header-title {
    font-size: 2.5rem !important;
    font-weight: 700 !important;
    color: white !important;
    margin-bottom: var(--space-3) !important;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
}

.header-subtitle {
    font-size: 1.125rem !important;
    color: var(--primary-100) !important;
    font-weight: 400 !important;
}

.header-badge {
    display: inline-flex !important;
    align-items: center !important;
    gap: var(--space-2) !important;
    background: rgba(255, 255, 255, 0.2) !important;
    padding: var(--space-2) var(--space-4) !important;
    border-radius: var(--radius-full) !important;
    font-size: 0.875rem !important;
    color: white !important;
    margin-top: var(--space-4) !important;
}

/* =============================================================================
   Tab Styles
   ============================================================================= */
.tabs-container {
    background: transparent !important;
}

.tab-nav {
    background: var(--glass-bg) !important;
    border-radius: var(--radius-xl) !important;
    padding: var(--space-2) !important;
    margin-bottom: var(--space-6) !important;
    box-shadow: var(--glass-shadow) !important;
}

.tab-nav button {
    border-radius: var(--radius-lg) !important;
    padding: var(--space-3) var(--space-6) !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
    border: none !important;
    background: transparent !important;
    color: var(--gray-600) !important;
}

.tab-nav button:hover {
    background: var(--gray-100) !important;
    color: var(--gray-900) !important;
}

.tab-nav button.selected {
    background: var(--primary-500) !important;
    color: white !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
}

/* =============================================================================
   Chat Interface Styles
   ============================================================================= */
.chat-container {
    background: white !important;
    border-radius: var(--radius-2xl) !important;
    box-shadow: var(--glass-shadow) !important;
    overflow: hidden !important;
}

.chatbot {
    background: var(--gray-50) !important;
    border: none !important;
    border-radius: var(--radius-xl) !important;
}

.chatbot .message {
    padding: var(--space-4) var(--space-5) !important;
    margin: var(--space-3) var(--space-4) !important;
    border-radius: var(--radius-xl) !important;
    max-width: 80% !important;
    animation: messageSlide 0.3s ease !important;
}

@keyframes messageSlide {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.chatbot .message.user {
    background: linear-gradient(135deg, var(--primary-500) 0%, var(--primary-600) 100%) !important;
    color: white !important;
    margin-left: auto !important;
    border-bottom-right-radius: var(--space-1) !important;
}

.chatbot .message.bot {
    background: white !important;
    color: var(--gray-800) !important;
    border: 1px solid var(--gray-200) !important;
    border-bottom-left-radius: var(--space-1) !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
}

/* =============================================================================
   Input Styles
   ============================================================================= */
.input-container {
    background: white !important;
    border-top: 1px solid var(--gray-200) !important;
    padding: var(--space-4) !important;
}

.input-box {
    background: var(--gray-50) !important;
    border: 2px solid var(--gray-200) !important;
    border-radius: var(--radius-xl) !important;
    padding: var(--space-4) var(--space-5) !important;
    font-size: 1rem !important;
    transition: all 0.2s ease !important;
}

.input-box:focus {
    border-color: var(--primary-500) !important;
    box-shadow: 0 0 0 4px var(--primary-100) !important;
    outline: none !important;
}

/* =============================================================================
   Button Styles
   ============================================================================= */
.btn {
    border-radius: var(--radius-lg) !important;
    padding: var(--space-3) var(--space-5) !important;
    font-weight: 600 !important;
    font-size: 0.9375rem !important;
    transition: all 0.2s ease !important;
    border: none !important;
    cursor: pointer !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: var(--space-2) !important;
}

.btn-primary {
    background: linear-gradient(135deg, var(--primary-500) 0%, var(--primary-600) 100%) !important;
    color: white !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
}

.btn-primary:hover {
    background: linear-gradient(135deg, var(--primary-600) 0%, var(--primary-700) 100%) !important;
    box-shadow: 0 6px 16px rgba(59, 130, 246, 0.5) !important;
    transform: translateY(-1px) !important;
}

.btn-secondary {
    background: white !important;
    color: var(--gray-700) !important;
    border: 1px solid var(--gray-300) !important;
}

.btn-secondary:hover {
    background: var(--gray-50) !important;
    border-color: var(--gray-400) !important;
}

.btn-icon {
    width: 40px !important;
    height: 40px !important;
    padding: 0 !important;
    justify-content: center !important;
    border-radius: var(--radius-lg) !important;
}

/* =============================================================================
   Status Indicators
   ============================================================================= */
.status-indicator {
    display: inline-flex !important;
    align-items: center !important;
    gap: var(--space-2) !important;
    padding: var(--space-2) var(--space-3) !important;
    border-radius: var(--radius-full) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
}

.status-online {
    background: var(--success-50) !important;
    color: var(--success-600) !important;
}

.status-online::before {
    content: '' !important;
    width: 8px !important;
    height: 8px !important;
    background: var(--success-500) !important;
    border-radius: 50% !important;
    animation: pulse 2s infinite !important;
}

.status-offline {
    background: var(--error-50) !important;
    color: var(--error-600) !important;
}

.status-offline::before {
    content: '' !important;
    width: 8px !important;
    height: 8px !important;
    background: var(--error-500) !important;
    border-radius: 50% !important;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* =============================================================================
   Sidebar Styles
   ============================================================================= */
.sidebar {
    background: var(--glass-bg) !important;
    backdrop-filter: blur(20px) !important;
    border-radius: var(--radius-2xl) !important;
    padding: var(--space-6) !important;
    border: 1px solid var(--glass-border) !important;
}

.sidebar-section {
    margin-bottom: var(--space-6) !important;
}

.sidebar-title {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: var(--gray-500) !important;
    margin-bottom: var(--space-3) !important;
}

.sidebar-item {
    display: flex !important;
    align-items: center !important;
    gap: var(--space-3) !important;
    padding: var(--space-3) !important;
    border-radius: var(--radius-lg) !important;
    color: var(--gray-700) !important;
    transition: all 0.2s ease !important;
}

.sidebar-item:hover {
    background: var(--gray-100) !important;
    color: var(--gray-900) !important;
}

/* =============================================================================
   Info Cards
   ============================================================================= */
.info-card {
    background: white !important;
    border-radius: var(--radius-xl) !important;
    padding: var(--space-5) !important;
    border: 1px solid var(--gray-200) !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
}

.info-card-title {
    font-size: 0.875rem !important;
    font-weight: 600 !important;
    color: var(--gray-900) !important;
    margin-bottom: var(--space-2) !important;
}

.info-card-value {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: var(--primary-600) !important;
}

/* =============================================================================
   Scrollbar Styles
   ============================================================================= */
::-webkit-scrollbar {
    width: 8px !important;
    height: 8px !important;
}

::-webkit-scrollbar-track {
    background: var(--gray-100) !important;
    border-radius: var(--radius-full) !important;
}

::-webkit-scrollbar-thumb {
    background: var(--gray-400) !important;
    border-radius: var(--radius-full) !important;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--gray-500) !important;
}

/* =============================================================================
   Responsive Design
   ============================================================================= */
@media (max-width: 768px) {
    .header-title {
        font-size: 1.875rem !important;
    }
    
    .main-container {
        padding: var(--space-4) !important;
    }
    
    .glass-card {
        padding: var(--space-4) !important;
    }
}

/* =============================================================================
   Loading States
   ============================================================================= */
.loading {
    position: relative !important;
    overflow: hidden !important;
}

.loading::after {
    content: '' !important;
    position: absolute !important;
    top: 0 !important;
    left: -100% !important;
    width: 100% !important;
    height: 100% !important;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent) !important;
    animation: shimmer 1.5s infinite !important;
}

@keyframes shimmer {
    100% { left: 100%; }
}

/* =============================================================================
   Dark Mode Styles
   ============================================================================= */
/* Dark mode variables */
.dark {
    --primary-50: #1e3a5f;
    --primary-100: #1a365d;
    --primary-200: #2c5282;
    --primary-300: #3182ce;
    --primary-400: #4299e1;
    --primary-500: #63b3ed;
    --primary-600: #90cdf4;
    --primary-700: #bee3f8;
    --primary-800: #e0f2fe;
    --primary-900: #f0f9ff;

    --gray-50: #1a1a2e;
    --gray-100: #16213e;
    --gray-200: #1f2937;
    --gray-300: #374151;
    --gray-400: #4b5563;
    --gray-500: #6b7280;
    --gray-600: #9ca3af;
    --gray-700: #d1d5db;
    --gray-800: #e5e7eb;
    --gray-900: #f9fafb;

    --glass-bg: rgba(26, 32, 44, 0.95);
    --glass-border: rgba(255, 255, 255, 0.1);
    --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

/* Bot Integration Card Styles */
.bot-card {
    background: linear-gradient(135deg, var(--gray-100) 0%, var(--gray-200) 100%) !important;
    border: 1px solid var(--gray-300) !important;
    border-radius: var(--radius-xl) !important;
    padding: var(--space-5) !important;
    margin-bottom: var(--space-4) !important;
    transition: all 0.3s ease !important;
}

.bot-card:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2) !important;
}

.bot-card-header {
    display: flex !important;
    align-items: center !important;
    gap: var(--space-3) !important;
    margin-bottom: var(--space-3) !important;
}

.bot-icon {
    width: 40px !important;
    height: 40px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    border-radius: var(--radius-lg) !important;
    font-size: 1.5rem !important;
}

.bot-icon-telegram { background: linear-gradient(135deg, #0088cc 0%, #229ED9 100%) !important; }
.bot-icon-whatsapp { background: linear-gradient(135deg, #25D366 0%, #128C7E 100%) !important; }
.bot-icon-slack { background: linear-gradient(135deg, #4A154B 0%, #611f69 100%) !important; }
.bot-icon-discord { background: linear-gradient(135deg, #5865F2 0%, #7289DA 100%) !important; }

.bot-status-badge {
    padding: var(--space-1) var(--space-3) !important;
    border-radius: var(--radius-full) !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
}

.bot-status-configured { background: var(--success-500) !important; color: white !important; }
.bot-status-pending { background: var(--warning-500) !important; color: white !important; }
.bot-status-disabled { background: var(--gray-500) !important; color: white !important; }

/* Model Card Styles */
.model-card {
    background: linear-gradient(135deg, var(--gray-100) 0%, var(--gray-200) 100%) !important;
    border: 2px solid var(--gray-300) !important;
    border-radius: var(--radius-lg) !important;
    padding: var(--space-4) !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    min-width: 120px !important;
    text-align: center !important;
}

.model-card:hover {
    border-color: var(--primary-500) !important;
    background: linear-gradient(135deg, var(--primary-900) 0%, var(--gray-200) 100%) !important;
    transform: scale(1.02) !important;
}

.model-card.selected {
    border-color: var(--primary-500) !important;
    background: linear-gradient(135deg, var(--primary-800) 0%, var(--primary-900) 100%) !important;
    box-shadow: 0 0 0 3px var(--primary-500), 0 4px 12px rgba(59, 130, 246, 0.3) !important;
}

.model-card-icon {
    font-size: 2rem !important;
    margin-bottom: var(--space-2) !important;
}

.model-card-name {
    font-weight: 600 !important;
    color: var(--gray-800) !important;
    font-size: 0.9rem !important;
}

.model-card-desc {
    font-size: 0.75rem !important;
    color: var(--gray-600) !important;
    margin-top: var(--space-1) !important;
}

/* Provider Server Card */
.server-card {
    background: var(--gray-100) !important;
    border: 1px solid var(--gray-300) !important;
    border-radius: var(--radius-lg) !important;
    padding: var(--space-4) !important;
    margin-bottom: var(--space-3) !important;
}

.server-card-header {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
}

.server-icon {
    width: 36px !important;
    height: 36px !important;
    background: var(--primary-600) !important;
    border-radius: var(--radius-md) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    color: white !important;
    font-size: 1.2rem !important;
}

/* Section Headers with Icons */
.section-header {
    display: flex !important;
    align-items: center !important;
    gap: var(--space-3) !important;
    padding: var(--space-4) !important;
    background: linear-gradient(135deg, var(--gray-100) 0%, var(--gray-200) 100%) !important;
    border-radius: var(--radius-lg) !important;
    margin-bottom: var(--space-4) !important;
    border-left: 4px solid var(--primary-500) !important;
}

.section-icon {
    font-size: 1.5rem !important;
}

/* Model Selection Buttons */
.model-select-btn {
    min-width: 140px !important;
    padding: 16px 24px !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    transition: all 0.3s ease !important;
    background: linear-gradient(135deg, #334155 0%, #1e293b 100%) !important;
    border: 2px solid #475569 !important;
    color: #f1f5f9 !important;
}

.model-select-btn:hover {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
    border-color: #60a5fa !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(59, 130, 246, 0.3) !important;
}

.model-select-btn.selected {
    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
    border-color: #60a5fa !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3), 0 8px 24px rgba(59, 130, 246, 0.4) !important;
}

/* Settings Title */
.settings-title {
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: #3b82f6 !important;
    margin-bottom: 1.5rem !important;
    padding-bottom: 0.75rem !important;
    border-bottom: 2px solid #334155 !important;
}

/* Accordion Styles for Dark Theme */
.gr-accordion {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
    border: 1px solid #334155 !important;
    border-radius: 12px !important;
    margin-bottom: 12px !important;
}

.gr-accordion > .label-wrap {
    padding: 16px !important;
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
    border-radius: 12px !important;
}

.gr-accordion > .label-wrap:hover {
    background: linear-gradient(135deg, #334155 0%, #1e293b 100%) !important;
}

/* Models Info Text */
.models-info {
    padding: 12px 16px !important;
    background: #0f172a !important;
    border-radius: 8px !important;
    margin-top: 12px !important;
    color: #94a3b8 !important;
    font-size: 0.9rem !important;
}

/* Form Group Styles */
.gr-group {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    margin-bottom: 16px !important;
}

/* Improve Dropdown Appearance */
.gr-dropdown {
    background: #1e293b !important;
    border-color: #475569 !important;
    border-radius: 8px !important;
}

.gr-dropdown:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2) !important;
}

/* Button Improvements */
.gr-button-primary {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
    border: none !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3) !important;
}

.gr-button-primary:hover {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4) !important;
}

.gr-button-secondary {
    background: #334155 !important;
    border: 1px solid #475569 !important;
    color: #e2e8f0 !important;
}

.gr-button-secondary:hover {
    background: #475569 !important;
    border-color: #64748b !important;
}

/* Checkbox and Switch Styles */
.gr-checkbox input[type="checkbox"]:checked + span {
    background: #3b82f6 !important;
}

/* Slider Styles */
.gr-slider input[type="range"] {
    accent-color: #3b82f6 !important;
}

/* Textbox Focus State */
.gr-textbox:focus-within {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2) !important;
}
"""

# =============================================================================
# Check available servers on startup
# =============================================================================
print("\n" + "=" * 60)
print("🔍 Detecting available LLM servers...")
print("=" * 60)

local_servers = ["ollama", "mlx", "lmstudio", "vllm"]
any_running = False

for name in local_servers:
    is_running, status = check_local_server_status(name)
    status_icon = "✅" if is_running else "❌"
    print(f"  {name:15} | {status}")
    if is_running:
        any_running = True

current_provider = config.LLM_PROVIDER
if current_provider in local_servers:
    is_running, _ = check_local_server_status(current_provider)
    if not is_running:
        print(f"\n⚠️  WARNING: Current provider '{current_provider}' is not running!")
        print(f"   Start it with: {get_server_start_command(current_provider)}")
        print(f"   Or switch to another provider in the Settings tab.")
        
        for name in local_servers:
            if name != current_provider:
                alt_running, _ = check_local_server_status(name)
                if alt_running:
                    print(f"\n💡 Tip: {name} is running. You can switch to it in Settings.")
                    break

print("=" * 60 + "\n")

# =============================================================================
# Initialize bot components
# =============================================================================
session_manager = SessionManager(config.SESSION_DATA_DIR)
llm_config = config.LLM_PROVIDERS[config.LLM_PROVIDER]
llm_provider = LLMProviderFactory.from_dict(llm_config)
router = MessageRouter(session_manager, llm_provider)

app_state = AppState(
    session_manager=session_manager,
    router=router,
    current_provider=config.LLM_PROVIDER
)

print("coco B initialized!")
print(f"Provider: {llm_provider.provider_name}")
print(f"Model: {llm_provider.model_name}")
print(f"Endpoint: {llm_provider.config.base_url}")

# =============================================================================
# Helper Functions with Icons
# =============================================================================

def reset_conversation(user_id):
    """Reset the current conversation"""
    session_key = session_manager.get_session_key("gradio", user_id)
    session_manager.reset_session(session_key)
    return [], "🔄 Conversation reset! Starting fresh. ✨"

def get_session_info(user_id):
    """Get current session statistics"""
    session_key = session_manager.get_session_key("gradio", user_id)
    stats = session_manager.get_session_stats(session_key)

    if not stats:
        return "📭 No active session"

    provider_info = app_state.get_current_provider_info()

    return f"""📊 **Session Statistics**

🆔 **Session ID**: `{stats['sessionId']}`
💬 **Messages**: {stats['messageCount']}
🤖 **Provider**: {provider_info['provider_name']}
🧠 **Model**: {provider_info['model_name']}
📅 **Created**: {datetime.fromtimestamp(stats['createdAt']).strftime('%Y-%m-%d %H:%M:%S')}
🕐 **Last Updated**: {datetime.fromtimestamp(stats['updatedAt']).strftime('%Y-%m-%d %H:%M:%S')}
📡 **Channel**: {stats['channel']}
"""

def load_conversation_history(user_id):
    """Load and display conversation history from JSONL"""
    session_key = session_manager.get_session_key("gradio", user_id)
    history = session_manager.get_conversation_history(session_key)

    if not history:
        return "📭 No conversation history"

    output = "📜 **Full Conversation History** (from JSONL file)\n\n"
    for i, msg in enumerate(history, 1):
        icon = "👤" if msg['role'] == 'user' else "🤖"
        output += f"{i}. {icon} **{msg['role'].title()}**: {msg['content']}\n\n"

    return output

def get_current_model_info():
    """Get current model info for display"""
    info = app_state.get_current_provider_info()
    return f"{info['provider_name']}: {info['model_name']}"

def get_server_status():
    """Get status of available LLM servers"""
    local_servers = ["ollama", "mlx", "lmstudio", "vllm"]
    
    status_text = "## 🖥️ LLM Server Status\n\n"
    for name in local_servers:
        is_running, status_msg = check_local_server_status(name)
        icon = "🟢" if is_running else "🔴"
        status_text += f"{icon} **{name.upper()}**: {status_msg}\n"
    
    status_text += "\n💡 Use the Settings tab to switch providers"
    return status_text

# =============================================================================
# Modern Gradio Interface
# =============================================================================

with gr.Blocks(
    title="coco B - AI Assistant"
) as demo:

    # =============================================================================
    # Modern Header
    # =============================================================================
    with gr.Row(elem_classes="header-container"):
        gr.Markdown("""
        <div style="text-align: center; padding: 2rem;">
            <img src="file/icon/coco_b_icon.png" alt="coco B" style="width: 80px; height: 80px; margin-bottom: 0.5rem;">
            <h1 style="font-size: 2.5rem; font-weight: 700; color: white; margin-bottom: 0.5rem;">
                coco B
            </h1>
            <p style="font-size: 1.125rem; color: rgba(255,255,255,0.9); margin-bottom: 1rem;">
                Your Intelligent AI Assistant with Persistent Memory
            </p>
            <div style="display: inline-flex; align-items: center; gap: 0.5rem; background: rgba(255,255,255,0.2); padding: 0.5rem 1rem; border-radius: 9999px; font-size: 0.875rem; color: white;">
                <span>🟢</span>
                <span>Ready to chat</span>
                <span>•</span>
                <span>Secure & Private</span>
            </div>
        </div>
        """)

    # =============================================================================
    # Main Content Tabs
    # =============================================================================
    with gr.Tabs(elem_classes="tabs-container"):
        
        # =========================================================================
        # Chat Tab
        # =========================================================================
        with gr.Tab("💬 Chat", id="chat"):
            with gr.Row():
                # Main chat area
                with gr.Column(scale=3):
                    # User info bar
                    with gr.Row(elem_classes="glass-card"):
                        with gr.Column(scale=2):
                            user_id = gr.Textbox(
                                label="👤 User ID",
                                value="user-001",
                                placeholder="Enter user ID...",
                                info="Each user gets their own conversation memory"
                            )
                        with gr.Column(scale=2):
                            model_info = gr.Textbox(
                                label="🤖 Current Model",
                                value=get_current_model_info(),
                                interactive=False
                            )
                        with gr.Column(scale=1):
                            refresh_model_btn = gr.Button("🔄 Refresh", size="sm")
                    
                    # Chat interface
                    chatbot = gr.Chatbot(
                        label="Conversation",
                        height=550,
                        elem_classes="chat-container"
                    )
                    
                    # Input area
                    with gr.Row():
                        msg = gr.Textbox(
                            label="💭 Your Message",
                            placeholder="Type your message here... (try /help for commands)",
                            scale=4,
                            show_label=False,
                            container=False
                        )
                        send_btn = gr.Button("📤 Send", variant="primary", scale=1)
                    
                    # Action buttons
                    with gr.Row():
                        reset_btn = gr.Button("🔄 Reset Chat", variant="secondary", size="sm")
                        stats_btn = gr.Button("📊 Statistics", variant="secondary", size="sm")
                        history_btn = gr.Button("📜 History", variant="secondary", size="sm")
                
                # Sidebar
                with gr.Column(scale=1):
                    # Server status
                    with gr.Column(elem_classes="sidebar"):
                        gr.Markdown("### 🖥️ Server Status")
                        server_status = gr.Markdown(get_server_status())
                        refresh_status_btn = gr.Button("🔄 Refresh Status", size="sm")
                        
                        gr.Markdown("---")
                        
                        # Quick tips
                        gr.Markdown("""
                        ### 💡 Quick Tips
                        
                        **Commands:**
                        • `/help` - Show all commands
                        • `/reset` - Start fresh
                        • `/stats` - View statistics
                        • `/skills` - List skills
                        
                        **Features:**
                        • 💾 Persistent memory
                        • 🔄 Context management
                        • 👥 Multi-user support
                        • ⚡ Hot-swap providers
                        """)
                        
                        gr.Markdown("---")
                        
                        # Session info
                        info_box = gr.Markdown(
                            "📭 **Session Info**\n\nNo active session yet. Start chatting!"
                        )

        # =========================================================================
        # Settings Tab
        # =========================================================================
        with gr.Tab("⚙️ Settings", id="settings"):
            create_provider_tab(app_state, model_info_component=model_info)
        
        # =========================================================================
        # Skills Tab
        # =========================================================================
        with gr.Tab("🛠️ Skills", id="skills"):
            create_skills_tab(app_state)

    # =============================================================================
    # Event Handlers
    # =============================================================================
    
    async def submit_message(message, history, user_id):
        """Handle message submission with streaming"""
        if not message.strip():
            yield history
            return
        
        # Add user message immediately
        history = history + [[message, None]]
        yield history
        
        # Stream the response
        async for updated_history in chat_with_bot(message, history, user_id, app_state):
            yield updated_history

    # Wire up events
    send_btn.click(
        fn=submit_message,
        inputs=[msg, chatbot, user_id],
        outputs=[chatbot],
        queue=True
    )
    
    msg.submit(
        fn=submit_message,
        inputs=[msg, chatbot, user_id],
        outputs=[chatbot],
        queue=True
    )
    
    reset_btn.click(
        fn=reset_conversation,
        inputs=[user_id],
        outputs=[chatbot, info_box]
    )
    
    stats_btn.click(
        fn=get_session_info,
        inputs=[user_id],
        outputs=[info_box]
    )
    
    history_btn.click(
        fn=load_conversation_history,
        inputs=[user_id],
        outputs=[info_box]
    )
    
    refresh_model_btn.click(
        fn=get_current_model_info,
        inputs=[],
        outputs=[model_info]
    )
    
    refresh_status_btn.click(
        fn=get_server_status,
        inputs=[],
        outputs=[server_status]
    )

    # =============================================================================
    # Footer
    # =============================================================================
    gr.Markdown("""
    <div style="text-align: center; padding: 2rem; margin-top: 2rem; color: #6b7280; font-size: 0.875rem;">
        <p>🔒 <strong>Secure & Private</strong> • All conversations stored locally in JSONL files</p>
        <p>Made with ❤️ by <strong>Idrak AI Ltd</strong> • Open Source - Safe Community Project</p>
    </div>
    """)

# =============================================================================
# Free port function (safe version using psutil)
# =============================================================================

def free_port(port: int) -> bool:
    """Safely kill process using specified port"""
    try:
        import psutil
        killed = False
        for conn in psutil.net_connections():
            if conn.laddr and conn.laddr.port == port and conn.pid:
                try:
                    proc = psutil.Process(conn.pid)
                    proc.terminate()
                    proc.wait(timeout=3)
                    killed = True
                except psutil.TimeoutExpired:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
        return killed
    except ImportError:
        print(f"⚠️  psutil not installed. Cannot auto-free port {port}.")
        return False

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    # Free the port before starting
    free_port(config.GRADIO_PORT)
    
    print("\n" + "=" * 60)
    print("🚀 Starting coco B Modern Interface")
    print("=" * 60)
    print(f"🤖 Bot Name: coco B")
    print(f"🧠 Provider: {llm_provider.provider_name}")
    print(f"🎯 Model: {llm_provider.model_name}")
    print(f"🌐 URL: http://localhost:{config.GRADIO_PORT}")
    print("=" * 60 + "\n")
    
    # Launch with modern settings - Dark mode default
    from coco_b import PROJECT_ROOT
    icon_dir = str(PROJECT_ROOT / "icon")

    # Create dark theme
    dark_theme = gr.themes.Base(
        primary_hue=gr.themes.colors.blue,
        secondary_hue=gr.themes.colors.indigo,
        neutral_hue=gr.themes.colors.slate,
    ).set(
        body_background_fill="#0f172a",
        body_background_fill_dark="#0f172a",
        block_background_fill="#1e293b",
        block_background_fill_dark="#1e293b",
        block_border_color="#334155",
        block_border_color_dark="#334155",
        block_label_background_fill="#1e293b",
        block_label_background_fill_dark="#1e293b",
        block_title_text_color="#f1f5f9",
        block_title_text_color_dark="#f1f5f9",
        body_text_color="#e2e8f0",
        body_text_color_dark="#e2e8f0",
        body_text_color_subdued="#94a3b8",
        body_text_color_subdued_dark="#94a3b8",
        button_primary_background_fill="#3b82f6",
        button_primary_background_fill_dark="#3b82f6",
        button_primary_background_fill_hover="#2563eb",
        button_primary_background_fill_hover_dark="#2563eb",
        button_primary_text_color="#ffffff",
        button_primary_text_color_dark="#ffffff",
        button_secondary_background_fill="#334155",
        button_secondary_background_fill_dark="#334155",
        button_secondary_text_color="#e2e8f0",
        button_secondary_text_color_dark="#e2e8f0",
        input_background_fill="#1e293b",
        input_background_fill_dark="#1e293b",
        input_border_color="#475569",
        input_border_color_dark="#475569",
        input_placeholder_color="#64748b",
        input_placeholder_color_dark="#64748b",
        shadow_drop="0 4px 6px -1px rgba(0, 0, 0, 0.3)",
        shadow_drop_lg="0 10px 15px -3px rgba(0, 0, 0, 0.3)",
    )

    demo.launch(
        server_name=config.HOST,
        server_port=config.GRADIO_PORT,
        share=False,
        show_error=True,
        quiet=False,
        css=CUSTOM_CSS,
        allowed_paths=[icon_dir],
        theme=dark_theme
    )
