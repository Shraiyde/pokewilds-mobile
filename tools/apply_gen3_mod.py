#!/usr/bin/env python3
"""Apply the BansheeStudio Gen 3 Overhaul mod (GameBanana 454615, v1.4.2)
onto this repo's project/ assets, in place, before the Godot export.

Usage:
    python3 tools/apply_gen3_mod.py <mod-zip-path> [project-root]

The mod zip is the GameBanana file 089v142.zip (Pokewilds 0.8.9, mod v1.4.2).
Its layout inside the zip (under "BansheeStudio's 3rd Gen Overhaul Mod/"):
    mods/tiles/*.png            -> project/assets/source_0_8_11/tiles/** (by basename)
    mods/battle/*.png           -> project/assets/**/battle/* (prefer source_exact/source_ui)
    mods/menu/*.png             -> project/assets/**/menu/*   (prefer source_exact/source_ui)
    mods/player/<char>/*.png    -> project/assets/gen3_players/<char>/*
    mods/music/*.ogg            -> project/assets/environment/music/* (prefer)
    mods/sounds/*               -> project/assets/** (by basename, prefer environment)
    !EARLY ACCESS/pokemon/<species>/*.png
                                -> project/assets/original_pokemon/<species>/*
    !... Optionals/             -> skipped (optional variants, not applied)

Files are only overwritten when a target with the same basename exists in the
repo (tiles/battle/menu/music/sounds) or the exact pokemon path exists.
A summary is printed at the end; exit code 0 even if some files are skipped.
"""
import os
import shutil
import sys
import zipfile
from collections import defaultdict

MOD_ROOT = "BansheeStudio's 3rd Gen Overhaul Mod/"


def index_by_basename(root, exts=(".png", ".ogg", ".wav")):
    """Map basename -> list of paths under root (recursive)."""
    idx = defaultdict(list)
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.lower().endswith(exts):
                idx[f].append(os.path.join(dirpath, f))
    return idx


def overlay_by_basename(mod_files, target_index, prefer_substr=(), skip_substr=("dark_mode", "lofi")):
    """Overwrite every repo file whose basename matches a mod file.

    prefer_substr: if given, only overwrite targets whose path contains one
    of these substrings (when any match exists); otherwise overwrite all.
    skip_substr: never overwrite targets whose path contains these.
    Returns (overwritten, skipped_no_match).
    """
    overwritten = 0
    skipped = 0
    for mod_path in mod_files:
        base = os.path.basename(mod_path)
        candidates = [p for p in target_index.get(base, [])
                      if not any(s in p for s in skip_substr)]
        if prefer_substr:
            preferred = [p for p in candidates
                         if any(s in p for s in prefer_substr)]
            if preferred:
                candidates = preferred
        if not candidates:
            skipped += 1
            continue
        for target in candidates:
            shutil.copyfile(mod_path, target)
            overwritten += 1
    return overwritten, skipped


def main():
    if len(sys.argv) < 2:
        print("usage: apply_gen3_mod.py <mod-zip-path> [project-root]")
        return 2
    zip_path = sys.argv[1]
    project_root = sys.argv[2] if len(sys.argv) > 2 else "project"
    project_root = os.path.abspath(project_root)

    tmp = os.path.join(os.path.dirname(os.path.abspath(zip_path)), "_gen3mod")
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
    mod_dir = os.path.join(tmp, MOD_ROOT)
    if not os.path.isdir(mod_dir):
        # Fall back: find the single top-level dir.
        subs = [d for d in os.listdir(tmp)
                if os.path.isdir(os.path.join(tmp, d))]
        mod_dir = os.path.join(tmp, subs[0]) if subs else tmp

    total_over = 0
    total_skip = 0

    def report(label, over, skip):
        nonlocal total_over, total_skip
        total_over += over
        total_skip += skip
        print(f"{label}: overwrote {over}, skipped (no repo match) {skip}")

    # --- Tiles: by basename under source_0_8_11/tiles (all subdirs) ---
    tiles_dir = os.path.join(project_root, "assets", "source_0_8_11", "tiles")
    tile_index = index_by_basename(tiles_dir, exts=(".png",))
    mod_tiles = []
    for dirpath, _dirs, files in os.walk(os.path.join(mod_dir, "mods", "tiles")):
        for f in files:
            if f.lower().endswith(".png"):
                mod_tiles.append(os.path.join(dirpath, f))
    over, skip = overlay_by_basename(mod_tiles, tile_index)
    report("tiles", over, skip)

    # --- Battle + menu UI: prefer source_exact / source_ui, skip dark_mode ---
    ui_index = index_by_basename(os.path.join(project_root, "assets"),
                                 exts=(".png",))
    for cat in ("battle", "menu"):
        cat_dir = os.path.join(mod_dir, "mods", cat)
        if not os.path.isdir(cat_dir):
            continue
        mod_files = []
        for dirpath, _dirs, files in os.walk(cat_dir):
            for f in files:
                if f.lower().endswith(".png"):
                    mod_files.append(os.path.join(dirpath, f))
        over, skip = overlay_by_basename(
            mod_files, ui_index,
            prefer_substr=("source_exact", "source_ui"),
            skip_substr=("dark_mode",))
        report(cat, over, skip)

    # --- Player sprites: mods/player/<char>/* -> gen3_players/<char>/* ---
    players_dir = os.path.join(project_root, "assets", "gen3_players")
    over = skip = 0
    player_dir = os.path.join(mod_dir, "mods", "player")
    if os.path.isdir(player_dir):
        for char in os.listdir(player_dir):
            src_char = os.path.join(player_dir, char)
            if not os.path.isdir(src_char):
                continue
            dst_char = os.path.join(players_dir, char)
            if not os.path.isdir(dst_char):
                skip += len([f for f in os.listdir(src_char)
                             if f.lower().endswith(".png")])
                print(f"player/{char}: no gen3_players/{char} dir, skipped")
                continue
            for f in os.listdir(src_char):
                if not f.lower().endswith(".png"):
                    continue
                dst = os.path.join(dst_char, f)
                if os.path.isfile(dst):
                    shutil.copyfile(os.path.join(src_char, f), dst)
                    over += 1
                else:
                    skip += 1
    report("player", over, skip)

    # --- Pokemon sprites: !EARLY ACCESS/pokemon/<species>/* -> original_pokemon/<species>/* ---
    pkm_src = os.path.join(mod_dir, "!EARLY ACCESS", "pokemon")
    pkm_dst = os.path.join(project_root, "assets", "original_pokemon")
    over = skip = 0
    if os.path.isdir(pkm_src):
        for species in os.listdir(pkm_src):
            src_sp = os.path.join(pkm_src, species)
            if not os.path.isdir(src_sp):
                continue
            dst_sp = os.path.join(pkm_dst, species)
            if not os.path.isdir(dst_sp):
                skip += len([f for f in os.listdir(src_sp)
                             if f.lower().endswith(".png")])
                continue
            for f in os.listdir(src_sp):
                if not f.lower().endswith(".png"):
                    continue
                dst = os.path.join(dst_sp, f)
                if os.path.isfile(dst):
                    shutil.copyfile(os.path.join(src_sp, f), dst)
                    over += 1
                else:
                    skip += 1
    report("pokemon", over, skip)

    # --- Music + sounds: prefer environment/, skip lofi/ ---
    audio_index = index_by_basename(os.path.join(project_root, "assets"),
                                    exts=(".ogg", ".wav"))
    for cat in ("music", "sounds"):
        cat_dir = os.path.join(mod_dir, "mods", cat)
        if not os.path.isdir(cat_dir):
            continue
        mod_files = []
        for dirpath, _dirs, files in os.walk(cat_dir):
            for f in files:
                if f.lower().endswith((".ogg", ".wav")):
                    mod_files.append(os.path.join(dirpath, f))
        over, skip = overlay_by_basename(
            mod_files, audio_index,
            prefer_substr=("environment",),
            skip_substr=("lofi",))
        report(cat, over, skip)

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"TOTAL: overwrote {total_over}, skipped {total_skip}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
