# Crop Shift — Farm Future Simulator

Web-based decision-support tool. "What happens to my farm if the future changes?"

## Run

```bash
cd web
pip install -r backend/requirements-web.txt
pip install -r ../requirements.txt
python run.py
```

Open http://localhost:8000

## Flow (6-step loop)

Scan → Plan → Simulate → Result → Learn → Rewind

1. **Scan** — drop a pin, NASA POWER/MODIS/SMAP data pulled for that field
2. **Plan** — soil inputs + priority sliders
3. **Simulate** — rotation engine scores candidates
4. **Result** — ranking, insights, risks, comparison table
5. **Learn** — C9 assistant explains in English + Bangla, voice readout
6. **Rewind** — one click back to baseline, or stress-test +2°C / −20% rain

## What-If presets

- Drought year (+1.5°C, −30% rain)
- Heat (+2°C)
- Heavy rain (+30%)
- Salinity stress
- Mars Dome Mode (zero rain stress + heat)

## Endpoints

- `GET /` — app
- `GET /api/health`
- `GET /api/crops`
- `POST /api/simulate` — full simulation
- `GET /api/climate/{lat}/{lon}` — history
