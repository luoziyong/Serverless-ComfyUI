import os
import json
import time
import urllib

import nodes
import requests
import folder_paths

class PromptExecutor:
    def __init__(self, server):
        self.outputs = {}
        self.object_storage = {}
        self.outputs_ui = {}
        self.old_prompt = {}
        self.server = server

    def download_image(self, path, url):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        response = requests.get(url, stream=True)
        if not response.ok:
            print(response)
            return
        with open(path, 'wb') as handle:
            for block in response.iter_content(1024):
                if not block:
                    break
                handle.write(block)

    def execute(self, prompt, prompt_id, extra_data={}, execute_outputs=[]):
        nodes.interrupt_processing(False)

        if "client_id" in extra_data:
            self.server.client_id = extra_data["client_id"]

        if self.server.client_id is None:
            print("No client id, not executing prompt")
            return

        endpoint_id = os.environ.get('ENDPOINT_ID', None)
        api_key = os.environ.get('API_KEY', None)

        url = f"https://api.runpod.ai/v2/{endpoint_id}/run"

        headers = {
            "Authorization":api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "input": {
                "client_id": self.server.client_id,
                "prompt": prompt,
                "extra_data": extra_data,
            }
        }

        print(payload)
        response = requests.post(url, headers=headers, json=payload)
        response_json = json.loads(response.text)
        status_url = f"https://api.runpod.ai/v2/{endpoint_id}/stream/{response_json['id']}"

        for i in range(120):
            time.sleep(1)
            print("Checking status...")

            response = requests.get(status_url, headers=headers)
            response_json = json.loads(response.text)
            print(response_json)

            stream = response_json["stream"]
            for item in stream:
                output = item["output"]
                if output["type"] == "executed":
                    data = output["data"]
                    unique_id = data["node"]
                    output_ui = data["output"]
                    self.outputs_ui[unique_id] = output_ui
                    for image in output_ui["images"]:
                        url = urllib.parse.urlparse(image["url"])
                        image_name = os.path.split(url.path) [1]
                        output_dir = folder_paths.get_directory_by_type(image["type"])
                        self.download_image(os.path.join(output_dir, image_name), image["url"])
                        image["filename"] = image_name
                        del image["url"]
                self.server.send_sync(output["type"], output["data"], self.server.client_id)

            if response_json["status"] == "COMPLETED":
                break
