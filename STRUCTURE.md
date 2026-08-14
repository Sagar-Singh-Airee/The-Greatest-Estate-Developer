# 🏗️ Project Architecture

This document outlines the internal structure of the estate_developer V10 agent module.

`	ext
estate_developer/
├── __init__.py
├── actions
│   └── __init__.py
├── agent.py
├── economics
│   ├── __init__.py
│   ├── crops.py
│   ├── market.py
│   ├── market_manager.py
│   ├── slot_allocator.py
│   └── town_forecaster.py
├── evaluation
├── execution
│   ├── hand_assignment.py
│   └── pathfinder.py
├── market
│   └── __init__.py
├── memory
├── opponent
│   ├── __init__.py
│   └── opponent_model.py
├── planning
│   ├── __init__.py
│   ├── beam_search.py
│   ├── endgame_planner.py
│   ├── generator.py
│   ├── production_capacity.py
│   ├── scheduler.py
│   └── tasks.py
├── scheduler
│   └── __init__.py
├── simulation
│   ├── state_copy.py
│   └── transition.py
├── state
│   ├── __init__.py
│   └── parser.py
├── strategic
│   ├── policy_guard.py
│   ├── terminal_value.py
│   └── trajectory_planner.py
├── tasks
│   └── __init__.py
└── telemetry
    └── __init__.py
`
