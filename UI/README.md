# Kung-Fu Chess UI

Full interactive UI for real-time chess engine built with OpenCV.

## Running the UI

```bash
python main.py
```

## Project Structure

- `main.py` — game loop entrypoint
- `server_bridge.py` — injects server/ onto sys.path
- `ui_config.py` — UI-only configuration
- `vendor/` — vendored `Img` class from course
- `assets/` — board image and sprite sets
- `graphics/` — rendering and window management
- `animation/` — piece animation and motion prediction
- `user_input/` — mouse click handling
- `state/` — observer pattern, game events, game facade
- `ui_components/` — UI panels (moves log, score, etc.)
- `tests/` — unit tests

## Features

✅ Real-time piece animation with state machines  
✅ Motion interpolation between board cells  
✅ Observer-based event system  
✅ Mouse click handling  
✅ Moves log display  
✅ Captured material scoring  
✅ Game over detection  

## Notes

- All graphics are rendered through the provided `Img` class per course rules
- UI logic is separated from server via the `GameFacade` adapter
- Tests cover pure-logic modules (timing, interpolation, observer, etc.)
