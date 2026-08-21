<div align="center">
  <h1>🏆 The Greatest Estate Developer</h1>
  <p><i>"Why would I work harder... when I can simply make the world work for me?"</i></p>
</div>

<br>

Welcome to **The Greatest Estate Developer**.

This is not a traditional farming bot. 

This is a comprehensive, predictive economic engine built to dominate the **Kaggriculture** leaderboard—a 30-day, 720-turn economic battlefield where land, labor, crops, livestock, fertilizer, and dynamic pricing dictate survival.

And naturally... **we intend to own the board.**

---

## 🏛️ The Premise

Two farmers. Two estates. One market. 720 turns.
And only one question matters at the end: **Who has the most cash?**

Kaggriculture looks like a cozy farming simulation. **It isn't.** 
Underneath the crops and livestock is a complex optimization problem involving:

- 🛣️ **Pathfinding & Labor Optimization** (Hungarian Algorithm)
- 📉 **Dynamic Pricing & Market Drain** (Town Consumption Forecasting)
- 🏗️ **Capital Investment & Expansion** (Hiring & Buying Land)
- 🧠 **Opponent Modeling** (Staggered selling to avoid crashes)
- 🔮 **Long-Horizon Planning** (Time-safe Forward Rollout Beam Search)

Every turn is a decision. Every decision has an opportunity cost. 
Every harvest changes the market. Every expansion consumes capital.

So we did not build an agent that merely *plays the game*. 
We built one that **understands the economy behind it.**

---

## ⚙️ The Architecture (V10 Ultimate)

The agent operates using a layered, state-advancing architecture. Check out the full breakdown in **[STRUCTURE.md](./STRUCTURE.md)**.

### 🧠 Strategic Trajectory Planner
The orchestrator. Evaluates the state and decides whether to run a deep future rollout, or execute the endgame liquidation policy.

### 🔭 Beam Search & True Rollouts
The agent doesn't guess. It uses a **Forward Rollout Beam Search** that perfectly clones the game environment. It plays out hundreds of simulated futures in memory, scores them using a rich **Terminal Value Calculator** (valuing cash, plants in the ground, and future animal yields), and picks the timeline that results in the highest wealth. Safe-guarded by a strict time limit to prevent Kaggle timeouts.

### ⚔️ Opponent Intelligence
The **Opponent Model** spies on the enemy's farm. It tracks their dominant crop and predicts their sell volume. Our **Market Manager** uses this intelligence to stagger our sell orders, ensuring we don't crash the market price alongside them.

### 🚜 Global Optimal Execution
When it's time to work, the **Task Generator** queues up everything that needs doing. Then, the **Hand Assignment Solver** uses the Hungarian algorithm to globally optimize the paths of all farm hands, guaranteeing the absolute minimum walking distance.

---

## 🚀 How to Submit to Kaggle

Because the agent is complex and spread across a highly organized module, we provide a build script to package it for the Kaggle platform.

1. Ensure your logic in `src/estate_developer` is complete.
2. Run the build script:
   ```bash
   python kaggle/build_submission.py
   ```
3. A single file `submission.py` will be generated in the `kaggle/` folder.
4. **Upload `kaggle/submission.py` to the Kaggle competition!** 

---

<div align="center">
  <i>Every mistake compounds. Every efficiency compounds. Build the greatest estate.</i>
</div>
This is the best estate game
