import mindspore as ms
from mindnlp.transformers import AlignModel, AlignProcessor
from mindspore import Tensor
import numpy as np
from PIL import Image
from pycocotools.coco import COCO
import os
from tqdm import tqdm  # 用于显示进度条

# Set the context to use CPU (or GPU if available)
ms.set_context(mode=ms.GRAPH_MODE, device_target="CPU")  # or "GPU" if you have a GPU

# Step 1: Specify the model name (Hugging Face's align model)
model_name = "kakaobrain/align-base"

# Step 2: Load the processor
processor = AlignProcessor.from_pretrained(model_name)

# Step 3: Load the model
model = AlignModel.from_pretrained(model_name)

# Step 4: Load the MSCOCO dataset
dataDir = 'E:\Code\Dataset\MSCOCO'  # Replace with the path to your MSCOCO dataset
dataType = 'val2017'
annFile = f'{dataDir}/annotations/captions_{dataType}.json'
coco = COCO(annFile)

# Step 5: Prepare input data
def get_image_and_caption(coco, img_id, dataDir):
    ann_ids = coco.getAnnIds(imgIds=img_id)
    anns = coco.loadAnns(ann_ids)
    caption = anns[0]['caption']  # Use the first caption for simplicity
    img_info = coco.loadImgs(img_id)[0]
    img_path = os.path.join(dataDir, dataType, img_info['file_name'])
    image = Image.open(img_path)
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image, caption

# Step 6: Evaluate the model
def evaluate_model(coco, model, processor, dataDir):
    img_ids = coco.getImgIds()
    image_embeds_list = []
    text_embeds_list = []

    # Use tqdm to show progress
    for img_id in tqdm(img_ids, desc="Evaluating"):  # Evaluate on the entire dataset
        image, caption = get_image_and_caption(coco, img_id, dataDir)
        inputs = processor(text=caption, images=image, return_tensors="np")
        input_ids = Tensor(inputs["input_ids"].astype(np.int64))
        attention_mask = Tensor(inputs["attention_mask"].astype(np.int64))
        pixel_values = Tensor(inputs["pixel_values"])
        output = model(input_ids, attention_mask=attention_mask, pixel_values=pixel_values)

        # Collect embeddings
        image_embeds_list.append(output.image_embeds.asnumpy())
        text_embeds_list.append(output.text_embeds.asnumpy())

    # Convert to numpy arrays
    image_embeds = np.vstack(image_embeds_list)
    text_embeds = np.vstack(text_embeds_list)

    # Calculate I2T and T2I R@1
    i2t_r1 = calculate_recall(image_embeds, text_embeds, k=1)
    t2i_r1 = calculate_recall(text_embeds, image_embeds, k=1)

    print(f"MSCOCO I2T R@1: {i2t_r1}")
    print(f"MSCOCO T2I R@1: {t2i_r1}")

def calculate_recall(query_embeds, gallery_embeds, k=1):
    # Calculate cosine similarity
    query_embeds = query_embeds / np.linalg.norm(query_embeds, axis=1, keepdims=True)
    gallery_embeds = gallery_embeds / np.linalg.norm(gallery_embeds, axis=1, keepdims=True)
    similarity = np.dot(query_embeds, gallery_embeds.T)
    # Get the top-k indices
    top_k_indices = np.argsort(-similarity, axis=1)[:, :k]
    # Check if the correct match is in the top-k
    recall = np.mean(np.any(top_k_indices == np.arange(len(query_embeds))[:, None], axis=1))
    return recall

# Step 7: Run the evaluation
evaluate_model(coco, model, processor, dataDir)
