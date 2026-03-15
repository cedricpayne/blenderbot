"""Polyhaven asset integration - download and use free 3D models and HDRIs."""

import json
import time
import requests
from hashlib import md5
from pathlib import Path
from tempfile import gettempdir

from .base import ToolsPackageBase


class PolyhavenHelper:
    """Helper for fetching and caching assets from Polyhaven's API."""

    url = "https://api.polyhaven.com"
    _assets_cache = {}
    _files_cache = {}

    @classmethod
    def fetch_assets(cls, asset_type: str) -> dict:
        """Fetch asset list with local file caching (2-day TTL)."""
        cache_file = Path(gettempdir()) / f"polyhaven_{asset_type}_cache.json"

        if cache_file.exists():
            if cache_file.stat().st_mtime > (time.time() - 60 * 60 * 24 * 2):
                if asset_type not in cls._assets_cache:
                    with open(cache_file) as f:
                        cls._assets_cache[asset_type] = json.load(f)
                return cls._assets_cache[asset_type]

        try:
            response = requests.get(f"{cls.url}/assets?t={asset_type}", timeout=30)
            response.raise_for_status()
            data = response.json()
            cache_file.write_text(json.dumps(data))
            cls._assets_cache[asset_type] = data
            return data
        except requests.RequestException as e:
            print(f"Error fetching Polyhaven assets: {e}")
            return {}

    @classmethod
    def fetch_model_files(cls, asset_id: str, resolution: str = "1k") -> dict:
        if asset_id not in cls._files_cache:
            try:
                response = requests.get(f"{cls.url}/files/{asset_id}", timeout=30)
                cls._files_cache[asset_id] = response.json().get("blend", {})
            except Exception:
                return {}

        res_int = int(resolution[:-1])
        best = "1k"
        for res in sorted(cls._files_cache[asset_id], key=lambda x: int(x[:-1])):
            if int(res[:-1]) <= res_int:
                best = res
        return cls._files_cache[asset_id].get(best, {}).get("blend", {})

    @classmethod
    def fetch_hdri_files(cls, asset_id: str, resolution: str = "1k") -> dict:
        if asset_id not in cls._files_cache:
            try:
                response = requests.get(f"{cls.url}/files/{asset_id}", timeout=30)
                cls._files_cache[asset_id] = response.json().get("hdri", {})
            except Exception:
                return {}

        res_int = int(resolution[:-1])
        best = "1k"
        for res in sorted(cls._files_cache[asset_id], key=lambda x: int(x[:-1])):
            if int(res[:-1]) <= res_int:
                best = res
        return cls._files_cache[asset_id].get(best, {})

    @classmethod
    def download_file(cls, url: str, save_path: str, expected_md5: str = None) -> str:
        path = Path(save_path)
        if path.exists():
            return save_path

        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading: {url}")
        response = requests.get(url, stream=True, timeout=120)
        data = b""
        for chunk in response.iter_content(chunk_size=8192):
            data += chunk

        if expected_md5 and md5(data).hexdigest() != expected_md5:
            raise ValueError(f"MD5 mismatch for {save_path}")

        with open(save_path, "wb") as f:
            f.write(data)
        return save_path

    @classmethod
    def download_model(cls, asset_id: str, resolution: str = "1k") -> dict:
        files = cls.fetch_model_files(asset_id, resolution)
        if not files:
            return {}

        cache_dir = Path(gettempdir()) / f"polyhaven_models/{asset_id}/{resolution}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        blend_path = (cache_dir / f"{asset_id}.blend").as_posix()

        cls.download_file(files["url"], blend_path, files.get("md5"))

        result = {"blend": blend_path}
        for fname, info in files.get("include", {}).items():
            if fname.startswith("textures/"):
                tex_path = cache_dir / fname
                tex_path.parent.mkdir(parents=True, exist_ok=True)
                cls.download_file(info["url"], tex_path.as_posix(), info.get("md5"))
                result[fname] = tex_path.as_posix()

        return result

    @classmethod
    def download_hdri(cls, asset_id: str, resolution: str = "1k") -> str:
        files = cls.fetch_hdri_files(asset_id, resolution)
        if not files:
            return ""

        # Prefer EXR over HDR
        file_info = files.get("exr") or files.get("hdr")
        if not file_info:
            return ""

        ext = "exr" if "exr" in files else "hdr"
        cache_dir = Path(gettempdir()) / f"polyhaven_hdris/{asset_id}/{resolution}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        hdri_path = (cache_dir / f"{asset_id}.{ext}").as_posix()

        return cls.download_file(file_info["url"], hdri_path, file_info.get("md5"))


class PolyhavenTools(ToolsPackageBase):
    """Search and use free 3D models and HDRIs from Polyhaven's online library."""

    def polyhaven_search_models(
        names: list[str] = None,
        tags: list[str] = None,
        categories: list[str] = None,
    ) -> dict:
        """
        Search Polyhaven for 3D models by name, tags, or categories.

        Args:
        - names: Model names to search for
        - tags: Tags to filter by (e.g. chair, wood, furniture)
        - categories: Categories to filter by (e.g. furniture, architecture)
        """
        assets = PolyhavenHelper.fetch_assets("models")
        names = names or []
        tags = tags or []
        categories = categories or []
        results = {}

        if names:
            matches = []
            for name_query in names:
                q = name_query.lower()
                for aid, asset in assets.items():
                    if q in asset["name"].lower():
                        matches.append(aid)
            results["name_matches"] = matches

        if tags:
            matches = []
            for tag in tags:
                q = tag.lower()
                for aid, asset in assets.items():
                    if q in asset.get("tags", []):
                        matches.append(aid)
            results["tag_matches"] = matches

        if categories:
            matches = []
            for cat in categories:
                q = cat.lower()
                for aid, asset in assets.items():
                    if q in asset.get("categories", []):
                        matches.append(aid)
            results["category_matches"] = matches

        return results

    def polyhaven_use_model(asset_id: str, resolution: str = "1k") -> dict:
        """
        Download and load a Polyhaven 3D model into the scene.

        Args:
        - asset_id: The Polyhaven asset ID (from search results)
        - resolution: Texture resolution (1k, 2k, 4k)
        """
        import bpy
        from mathutils import Vector

        files = PolyhavenHelper.download_model(asset_id, resolution)
        if "blend" not in files:
            raise ValueError(f"No blend file found for asset: {asset_id}")

        old_objects = set(bpy.data.objects)
        with bpy.data.libraries.load(files["blend"]) as (data_from, data_to):
            data_to.objects = data_from.objects

        new_objects = set(bpy.data.objects) - old_objects
        loaded_names = []
        for obj in new_objects:
            bpy.context.collection.objects.link(obj)
            loaded_names.append(obj.name)

        return {
            "asset_id": asset_id,
            "resolution": resolution,
            "loaded_objects": loaded_names,
        }

    def polyhaven_search_hdris(
        names: list[str] = None,
        tags: list[str] = None,
        categories: list[str] = None,
    ) -> dict:
        """
        Search Polyhaven for HDRI environment maps.

        Args:
        - names: HDRI names to search for
        - tags: Tags to filter by (e.g. outdoor, sunset, studio)
        - categories: Categories to filter by
        """
        assets = PolyhavenHelper.fetch_assets("hdris")
        names = names or []
        tags = tags or []
        categories = categories or []
        results = {}

        if names:
            matches = []
            for name_query in names:
                q = name_query.lower()
                for aid, asset in assets.items():
                    if q in asset["name"].lower():
                        matches.append(aid)
            results["name_matches"] = matches

        if tags:
            matches = []
            for tag in tags:
                q = tag.lower()
                for aid, asset in assets.items():
                    if q in asset.get("tags", []):
                        matches.append(aid)
            results["tag_matches"] = matches

        if categories:
            matches = []
            for cat in categories:
                q = cat.lower()
                for aid, asset in assets.items():
                    if q in asset.get("categories", []):
                        matches.append(aid)
            results["category_matches"] = matches

        return results

    def polyhaven_use_hdri(asset_id: str, resolution: str = "1k") -> dict:
        """
        Download and apply a Polyhaven HDRI as the scene's environment lighting.

        Args:
        - asset_id: The Polyhaven HDRI asset ID
        - resolution: HDRI resolution (1k, 2k, 4k, 8k)
        """
        import bpy

        hdri_path = PolyhavenHelper.download_hdri(asset_id, resolution)
        if not hdri_path:
            raise ValueError(f"Failed to download HDRI: {asset_id}")

        world = bpy.data.worlds.new(name=asset_id)
        world.use_nodes = True

        nodes = world.node_tree.nodes
        links = world.node_tree.links

        output = None
        for node in nodes:
            if node.type == "OUTPUT_WORLD":
                output = node
                break
        if not output:
            output = nodes.new("ShaderNodeOutputWorld")

        bg = None
        for node in nodes:
            if node.type == "BACKGROUND":
                bg = node
                break
        if not bg:
            bg = nodes.new("ShaderNodeBackground")
            links.new(bg.outputs["Background"], output.inputs["Surface"])

        env_tex = nodes.new("ShaderNodeTexEnvironment")
        env_tex.image = bpy.data.images.load(filepath=hdri_path)
        links.new(env_tex.outputs["Color"], bg.inputs["Color"])

        bpy.context.scene.world = world

        return {"asset_id": asset_id, "resolution": resolution, "hdri_path": hdri_path}
