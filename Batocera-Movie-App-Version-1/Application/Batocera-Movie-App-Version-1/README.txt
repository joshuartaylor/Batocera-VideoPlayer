BATOCERA MOVIE APP VERSION 1
============================
Theater interface build for Batocera 42 + Zaparoo

Created by Joshua R. Taylor • JRT3D.com • 2026
Developed with assistance from ChatGPT

VERSION 1 PUBLIC RELEASE
------------------------
- Public package name: Batocera-Movie-App-Version-1.zip.
- Movie-to-movie scans now reset pause, mute, default volume, fit/fill, zoom,
  restart-prompt and controller-bridge state for the newly selected movie.
- Keeps the fast persistent MPV handoff while preventing controls from staying
  attached to the previously playing movie.
- Uses Zaparoo's background lifecycle for the short launch client while the
  session manager owns persistent MPV. This removes Core's delayed blocking-
  process stop event so Play/Pause remains attached after every replacement.
- Waits and retries when Zaparoo reports background optimization or the
  British-spelled background optimisation used by Core 2.16.1.
- Keeps Joshua R. Taylor / JRT3D.com credit on the installer success and
  installed-version screens.
- Removes creator-credit overlays from the everyday Movies theater interface.
- Preserves the proven playback, controls, movie/game handoff, Carbon main
  menu, poster view, manual artwork and Zaparoo card behavior.

v2.2.0-beta45 ZAPAROO RENAME INDEX CLEANUP
------------------------------------------
- After a real movie filename is renamed through SHARE, Movie Player now asks
  Zaparoo Core to reindex only the Movie system.
- Waits for that selective index to complete, then removes the obsolete media
  row using Zaparoo's official media.clean.orphans operation.
- Does not rebuild or delete Zaparoo's user database, mappings, history,
  favorites, pairing or phone settings.
- Playback, handoff, controls and every locked theme asset remain unchanged.

v2.2.0-beta44 TITLE RENAME + NORMAL REFRESH MAINTENANCE
-------------------------------------------------------
- Preserves intentional movie-title edits made through Batocera metadata.
- A renamed movie receives its new filename-derived title without retaining a
  stale gamelist entry.
- GAME SETTINGS > UPDATE GAME LISTS remains the normal Batocera refresh route.
- Ports now labels the manual builder as Repair Movie Library - Only If Needed.
- Zaparoo title/poster changes require Update media database followed by a
  Movie metadata scrape; use Force/Full Rescrape when an old title is cached.
- Playback, movie/game handoff, controls, Carbon main menu and the custom
  two-panel Movies layout are unchanged from beta43.

v2.2.0-beta41 ISOLATED INTERNAL MOVIES VIEW SELECTION

- Sets only the per-system `movies.defaultView=detailed` preference so Carbon
  cannot replace the existing two-panel Movies library with its thumbnail grid.
- Restores the already-bundled left highlighted title list and right framed
  movie poster with readable metadata below it.
- Leaves Carbon in complete control of the inherited bottom help text, font,
  colors, controller icons, spacing, and placement.
- Does not modify the locked main-menu Movies system view, theater background,
  logo, blue rails, playback, controls, or movie/game handoff behavior.

v2.2.0-beta40 LOG-PROVEN GAME RECOVERY + RESTART CONFIRMATION

- Fixes the exact failure captured on August 31: after MPV released the display,
  the first EmulationStation process never exposed port 1234. The clean restart
  recovered the API but the pending game path was previously abandoned.
- Preserves that exact pending path across the clean frontend restart and then
  continues `/launch`, instead of stopping idle at Batocera's main menu.
- Clears all movie handoff ownership and markers after a verified launch
  failure so later game scans are never locked out.
- Select/Back now pauses the movie and displays `RESTART MOVIE FROM BEGINNING?`.
  A confirms; B cancels and resumes the movie; the prompt cancels after 12s.
- Does not modify the checksum-locked beta15 Movies theme or picture controls.

v2.2.0-beta39 TRUE BETA15 DEPLOYMENT + VERIFIED GAME START

- Restores beta15's actual deployment method at
  `/userdata/roms/movies/theme.xml`, not merely the same theme artwork inside a
  newer cloned-theme mechanism.
- Restores the user's original Carbon ThemeSet and removes the obsolete
  `movie-player-carbon` clone after the beta15 override is verified.
- Verifies that a scanned game actually starts after `/launch`; if Batocera
  remains at `NO GAME RUNNING`, retries the exact game path once.
- Maps controller Select/Back directly to restart from the beginning.
- Keeps B as movie exit and preserves all checksum-locked beta15 visuals.

v2.2.0-beta38 VERIFIED PLAYER STARTUP REPAIR

- Fixes a Linux process-detection bug: `pgrep -x emulationstation` cannot
  reliably match the 16-character executable through the 15-character process
  name field, so the player could leave Batocera holding the display.
- Detects the real frontend from `/proc/*/cmdline` without confusing the
  S31emulationstation init script for the application.
- Restores beta15's proven startup order: stop EmulationStation completely,
  then create the fullscreen MPV process.
- Corrects the diagnostic check for the Movies menu's verified launch bridge.
- Keeps the exact beta15 visual files unchanged and checksum locked.

v2.2.0-beta37 EXACT BETA15 VISUAL RESTORE + LOCK

- Restores the complete beta15 Movies theme byte-for-byte from the original
  beta15 package supplied by the project owner.
- Restores its Carbon carousel, theater background, Movies logo, highlighted
  left title list, large framed poster, and right-side movie information.
- Locks the six approved visual assets by SHA-256 regression tests so a future
  update fails testing instead of silently changing the approved presentation.
- Retains beta36 playback, Fit/Fill/Zoom, movie switching, game handoff,
  installer confirmation, diagnostics, and fast first-boot activation.

v2.2.0-beta36 FAST BOOT + BETA35 HANDOFF/RAILS CONSOLIDATION

- Reads the installed theme and EmulationStation settings on first boot.
- When ES already loaded the correct Movies theme—the normal case—records the
  activation immediately and skips the Carbon copy plus frontend restart.
- Retains the controlled restart only as a recovery fallback when the theme is
  genuinely missing or the saved ThemeSet is wrong.
- Includes beta35's explicit Carbon-blue carousel rails, exact real-process
  detection, three-stage loading, and post-display-release API verification.
- Does not modify the working Movies library/detail view.

v2.2.0-beta35 EXPLICIT CARBON RAILS + VERIFIED GAME API HANDOFF

- Draws the existing Carbon-blue top and bottom carousel rails explicitly over
  the theater background instead of relying on inherited theme z-order.
- Leaves the approved Movies logo, theater art, two-panel library, poster frame,
  movie switching, and Fit/Fill/Zoom artwork and behavior unchanged.
- Detects only the real `emulationstation` process; the S31 startup shell script
  can no longer create a false-ready result followed by a black screen.
- Shows stage two immediately after requesting the frontend asynchronously.
- Always shows stage three before giving up the MPV display.
- If the real ES API was blocked by fullscreen playback, releases the display,
  waits for the verified API, then submits the game launch exactly once.
- If the real API never appears, safely restores the frontend because no game
  launch request was issued and therefore cannot be interrupted by recovery.

v2.2.0-beta34 RESTORED MILESTONE + ATOMIC MEDIA SWITCHING

- Restores the byte-identical approved Movies logo, theater background, Carbon
  carousel, left title panel, right poster panel, and gold poster frame.
- Removes beta33's experimental same-name theme overlay.
- Activates the frozen `movie-player-carbon` theme during one controlled
  frontend restart on the first normal boot after installation.
- Shows the fullscreen movie before stopping EmulationStation behind it,
  preventing the side-menu flash during a movie card launch.
- Treats Core's old-launcher exit during a replacement scan as synthetic;
  the current MPV session remains alive and atomically loads the new movie.
- Delays frontend restoration after movie exit and cancels it when another
  movie or game has claimed the session.
- Starts EmulationStation asynchronously for game handoff so the loading screen
  can always advance beyond stage one while MPV still owns the display.

v2.2.0-beta33 LOCKED THEME + MOVIE DISPLAY OWNERSHIP

- Restores the exact approved Carbon/chrome Movies layout without redesigning it.
- Attempted a same-name Carbon overlay; beta34 removes this approach.
- Stops EmulationStation again if a Zaparoo movie-to-movie lifecycle event tries
  to reopen the Batocera menu over active movie playback.
- A guarded debounce leaves legitimate game handoffs fully in control.

v2.2.0-beta32 NON-BLOCKING GAME HANDOFF

- Keeps the proven movie switching, theme, and Fit/Fill/Zoom behavior unchanged.
- Shows all three loading stages for a guaranteed minimum time so the transition
  no longer looks frozen or instantly disappears.
- Sends the EmulationStation game launch request asynchronously, then releases
  the fullscreen movie display while that request remains active. This breaks
  the display deadlock that could leave a black screen instead of the game.
- Allows up to Batocera/Zaparoo's full launch timeout on slower hardware.
- Never restarts EmulationStation merely because its API stops answering during
  launch; that can mean the selected emulator has already taken control.
- Preserves the recent-movie-exit guard so a scan is not lost during transition.

v2.2.0-beta31 F1-SAFE INSTALLER + RESTART MOVIE

- Never stops, starts, restarts, or reboots EmulationStation during installation.
- Leaves the Batocera F1 desktop running throughout the entire process.
- Opens a foreground INSTALLATION SUCCESSFUL window containing the exact version,
  verification status, movie count, and Zaparoo status.
- Waits indefinitely for CLOSE INSTALLER, then returns to F1 for the user to
  close manually whenever ready.
- Adds restart-from-beginning on keyboard/Zaparoo R, controller L3, and Select+A.
- Restart seeks precisely to 0:00, resumes playback, and confirms visibly.

v2.2.0-beta30 HARDWARE-VISIBLE INSTALL + VERIFIED GAME HANDOFF

- Uses MPV—the same proven display path as movie playback—for a full-screen
  installation-success screen instead of terminal dialogs or a black framebuffer.
- Keeps that screen visible while EmulationStation starts underneath it, then
  reveals the already-running Batocera menu.
- Adds a dedicated accessible LOADING GAME screen with three visible stages.
- Fixes the race where Zaparoo's synthetic exit could close the movie just before
  Core logged the new game path, causing the selected game to be lost.
- Keeps the loading screen visible until the game launch request is accepted.
- Adds a 350 ms exit-event guard so a real B/Esc exits normally while a pending
  Zaparoo game scan takes ownership of the transition.

v2.2.0-beta25 RELEASE-CANDIDATE UX: CONFIRMED INSTALL + VISIBLE GAME LOADING

- Stops EmulationStation before replacing theme state, preventing the running
  frontend from writing the old thumbnail selection back over the installer.
- Installs a true `movie-player-carbon/movies/theme.xml`, the first location
  Batocera checks for this system inside the selected theme set.
- Deletes the stale ROM-folder override.
- Forces only `movies.defaultView` to the real detailed text-list renderer.

v2.2.0-beta17 FORCED REAL DETAILED MOVIES VIEW

- Uses Batocera 42's actual per-system `movies.defaultView=detailed` setting.
- Restores the real text-list renderer, left/right panels, framed poster and
  metadata instead of attempting to restyle Carbon's thumbnail renderer.
- Does not change the global view style or any other system's appearance.
- Removes the temporary writable Carbon-clone approach from beta16.

v2.2.0-beta16 CARBON-NATIVE MOVIES LIBRARY

- Replaces the ignored ROM-folder custom-view override with an exact writable
  clone of stock Carbon and Carbon's own layouts/movies_2.xml hook.
- Only Movies receives the left list, framed poster, and information layout.
- Every other page, including the help text and controller icons, remains stock
  Carbon because the installed theme is copied directly from Batocera 42.

v2.2.0-beta15 RESTORED MOVIES SELECTION SCREEN

- Restores the left highlighted title list and right framed movie poster even
  when Carbon remembers Icons, Tiles, Carousel, Boxes, or Content view mode.
- Keeps Carbon in complete control of the bottom help text and controller icons.
- Leaves the locked, working main Movies tab unchanged.

v2.2.0-beta14 CLEAR MOVIES LOGO + LOCKED THEME

- Replaces the cinema-marked menu artwork with the clearer MOVIES logo.
- Leaves the locked Carbon main-menu theme and two-panel Movies view unchanged.

v2.2.0-beta13 LOCKED MAIN MENU + FORCED TWO-PANEL MOVIES VIEW

- Fixes Batocera 42 Carbon, which uses a root default theme rather than the
  per-system template folders assumed by beta4/beta5.
- Removes the ROM-folder fallback theme after Carbon succeeds because Batocera
  gives that file priority over the selected theme set.
- Fill now handles 4:3 pictures baked into 1920x1080 pillarboxed video.
- Fit/Fill/Zoom use direct linear video-scale-x/y properties.
- Controller actions and calculated scale values persist in the diagnostic log.
- Always exports Movie-Player-Diagnostics.txt to the main SHARE folder.
- Also creates Movie-Player-Logs.zip when Batocera's zip command works.
- Captures Carbon selection, installed theme paths, free space, controller input,
  MPV logs, and live aspect/zoom properties while a movie is playing.
- Shows an unmistakable EXPORT SUCCESSFUL or LOG EXPORT FAILED screen.
- Clones the exact stock Carbon theme already installed on Batocera.
- Adds Movies as a native Carbon system page instead of imitating its style.
- Carbon owns fonts, colors, help icons, carousel, and metadata presentation.
- Keeps the theater background, Movies logo, and framed poster presentation.
- No Carbon download or multi-gigabyte upload is required.
- Replaces output-dependent panscan Fill with calculated video zoom.
- Detects the active movie and screen aspect ratios for an exact center crop.
- Makes Zoom steps visibly accurate at 115%, 130%, and 150%.
- Explicitly enables aspect-preserving video scaling in every launch path.
- Converts the frame's opaque white center into a true transparent poster window.
- Places poster artwork behind the gold frame and exactly within its opening.
- Keeps poster artwork centered and proportional without moving the information below it.
- Retains the corrected Logitech F310 X/Y fit, fill, and zoom controls.
- Removes the custom blue theme rules that conflicted with some Batocera themes.
---------------------
- Removes the added blue-rule overlay from the Movies carousel.
- Corrects Logitech F310 DirectInput X/Y button numbering.
- Moves the poster assembly fully below the right panel's upper border.
- Adds an inset black/gold mat so poster artwork cannot touch either frame.
- Keeps all movie information readable below the poster.

v2.1.5 NATIVE THEME MATCH
---------------------
- Copies the active theme's real carousel, help icons, font, and statistics style.
- Restores Batocera's native multi-line system information block.
- Matches the screenshot carousel height and blue-rule placement.
- Keeps the poster enlarged while reserving readable metadata beneath it.

v2.1.4 CAROUSEL + PICTURE CONTROLS
---------------------
- Restores blue rules around the translucent Movies carousel bar.
- Uses gray help text, blue help icons, and the active theme font when found.
- Restores guaranteed Movies, Favorites, and Played counters.
- Enlarges the gold poster presentation by approximately 50 percent.
- X explicitly switches Fit/Fill; Y cycles 110/120/130 percent Zoom and Off.

v2.1.3 CURRENT MEDIA + THEME POLISH
---------------------
- Quotes complex movie paths correctly for Zaparoo Current Media/Write Playing.
- Matches both Movies help bars to the active Batocera theme when possible.
- Keeps a consistent blue help-bar fallback when theme data is unavailable.
- Preserves the gold frame and poster aspect ratios above the right panel.

v2.1.2 THEATER LAYOUT LOCK
---------------------
- Restores the approved standalone theater Movies theme.
- Keeps the Movies system background static instead of using media previews.
- Fits custom poster artwork inside the supplied gold theater frame.
- Maps controller X and Y to picture Fit/Fill.

v2.1.1 PLAYBACK LOCK UPDATE
---------------------
- Guarantees manual playback with an automatic direct-player fallback.
- Keeps Zaparoo first in the route so Current Media still gets first priority.
- Precisely centers custom posters inside the illuminated white frame.
- Lets the active Batocera theme supply movie-list fonts and colors.

v2.1.0 THEATER UPDATE
---------------------
- Manual Batocera launches now route through Zaparoo Current Media.
- Preserves Batocera Favorites, play counts, last played and total playtime.
- Adds theater-curtain system artwork and illuminated poster presentation.
- Adds Fit/Fill picture modes for 4:3 movies (controller Y or keyboard F).
- Enlarges the Movies logo and adds subtle JRT3D creator credit.
- Does not edit or restart Zaparoo networking.

v2.0.2 CONNECTION FIX
---------------------
- Restores Zaparoo App access from phones on the same private home network.
- Uses Zaparoo's supported service restart instead of the unreliable reload.
- Keeps a backup of the prior Zaparoo config before changing phone access.
- Preserves the v2.0.1 filename/path and return-to-Movies fixes.

PURPOSE
-------
Play movies fullscreen without Kodi. One persistent session manager owns MPV,
movie replacement, controls, and Batocera restoration. Menu selections and
Zaparoo cards use the same player instead of competing launcher wrappers.

INSTALL
-------
1. Extract this ZIP to a USB drive.
2. In Batocera, press F1 to open the file manager.
3. Open the extracted batocera-movie-player folder.
4. Double-click install.sh and choose Execute.
5. Confirm that v2.2.0-beta25, THEME CHECK: PASSED and Phone access: PRESERVED are shown.
6. Return to Batocera and scan the existing movie card once.

The installer refreshes the Batocera menu automatically. Do not rebuild the
database or rewrite an existing movie card for this playback test.

PHONE SETUP
-----------
1. Open the Zaparoo App.
2. Open Settings > Manage Media.
3. Choose All systems.
4. Select Update media database.
5. When it finishes, use Search Media and select system Movie.

Do not use Repair Movies. It has been removed from this clean build.
Do not write movie cards using Path or hand-written ZapScript while testing.
Choose the movie from Zaparoo Search Media and write that result to the tag.

LOCKED PLAYBACK FLOW
--------------------
Open Movies and press A, or scan an existing movie card. Scanning another movie
uses MPV's loadfile replace command; it does not restart the player or Batocera.
Press B once to exit. The session manager restores and verifies EmulationStation.

MOVIE LOCATION
--------------
There is one movie library and one Zaparoo search path:

  /userdata/roms/movies

Network path:

  \\BATOCERA\share\roms\movies

The installer safely moves content from the obsolete /userdata/movies folder
into this folder. It does not create a duplicate compatibility link.

MANUAL POSTERS
--------------
Put an image beside the movie or inside images, thumbnails, or custom-posters.
Accepted formats: JPG, JPEG, PNG, WEBP and BMP.

Examples:

  The Goonies.mp4
  The Goonies-poster.jpg

  The Goonies.mp4
  images/The Goonies.png

  The Goonies.mp4
  custom-posters/The Goonies.webp

After adding or changing artwork, wait a moment and choose GAME SETTINGS >
UPDATE GAME LISTS. The movie index rebuilds automatically; the Ports refresh
entry remains only as a manual fallback. Run a Zaparoo local metadata scrape if
you also want the artwork imported into the phone app.

When no matching manual image or TMDB poster exists, the player can attempt a
free, no-account Apple movie-catalog artwork lookup. Results are stored locally. A matching
manual JPG, JPEG, PNG, WEBP or BMP always replaces an automatic result.

CONTROLS
--------
Controller A / keyboard Space     Play or pause
Controller B / keyboard Esc       Stop and return to Batocera
Controller Start                  Play or pause
Controller Select / Back          Restart movie from the beginning
D-pad Left / Right                Seek back/forward 10 seconds
L1 / R1                           Seek back/forward 60 seconds
D-pad Up / Down                   Volume
Controller X / keyboard F         Toggle picture Fit/Fill
Controller Y / keyboard Z         Cycle Zoom 110/120/130%/Off
Controller L3 / keyboard R        Restart movie from the beginning
Controller Select + A             Restart movie from the beginning
Start + Select / keyboard Q       Immediate emergency exit

Scanning a different movie card immediately switches movies.

PROGRESS
--------
Playback positions are preserved. Refresh Movie Library adds Continue Watching
percentages and watched markers to the Batocera Movies list.

VERSION AND LOGS
----------------
Check the installed version at:
Ports > Movie Player Version

Run the one-button status report at:
Ports > Movie Player Diagnostics

Logs:
  /userdata/system/logs/movie-player-install.log
  /userdata/system/logs/movie-player-diagnostics.log
  /userdata/system/logs/batocera-movie-player.log

UNINSTALL
---------
Run uninstall.sh. Movies, posters and playback progress are not deleted.
