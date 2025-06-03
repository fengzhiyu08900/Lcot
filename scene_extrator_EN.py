import json
import os
import re
from openai import OpenAI
from tqdm import tqdm
import argparse

class NovelCharacterEvents:
    def __init__(self):
        self.client = OpenAI(
            api_key="",
            base_url="https://www.dmxapi.com/v1/"
        )
        self.chunk_size = 4000  # 每个分块的最大字符数
        self.overlap = 500      # 分块之间的重叠字符数
        # 初始化空的角色别名字典
        self.character_aliases = {}
        self.filename = ""
        self.dir = ""
        
    def read_novel(self, file_name, dir):
        self.filename = file_name
        self.dir = dir
        """读取小说文件"""
        file_path = os.path.join(dir,file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            print(f"读取文件时出错: {str(e)}")
            return None

    def split_text(self, text):
        """将文本分成多个重叠的块"""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            if end < text_length:
                last_period = text[start:end].rfind('。')
                if last_period != -1:
                    end = start + last_period + 1
            
            chunks.append(text[start:end])
            start = end - self.overlap if end < text_length else end
            
        return chunks

    def identify_chapters(self, text):
        """识别小说中的章节"""
        # 匹配多种章节标题格式，确保前面至少有一个换行符
        chapter_patterns = [
            r'(?<=\n)\s*第[一二三四五六七八九十百千万零\d]+[章节回卷部篇幕场][ \t]*[^\n]*',
            r'(?<=\n)\s*Chapter[ \t]*\d+[ \t]*[^\n]*',
            r'(?<=\n)\s*(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY|THIRTY|FORTY|FIFTY|SIXTY|SEVENTY|EIGHTY|NINETY|HUNDRED|THOUSAND|MILLION|BILLION)(?:[\s-](?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE|THIRTEEN|FOURTEEN|FIFTEEN|SIXTEEN|SEVENTEEN|EIGHTEEN|NINETEEN|TWENTY|THIRTY|FORTY|FIFTY|SIXTY|SEVENTY|EIGHTY|NINETY|HUNDRED|THOUSAND|MILLION|BILLION))*[ \t]*[^\n]*', # 新增：匹配大写英文数字作为章节标题
            r'(?<=\n)\s*[A-Z][A-Z\s\d]*[A-Z][ \t]*[^\n]*', # 原有的全大写模式，需要调整顺序以避免吞噬
            r'(?<=\n)\s*\d+[、.][ \t]*[^\n]*'
        ]

        # 组合模式时建议使用非捕获组(?:)提升性能
        chapter_pattern = '|'.join(f'(?:{pattern})' for pattern in chapter_patterns)

        # 使用示例（建议添加UNICODE和MULTILINE标志）
        chapter_matches = list(re.finditer(chapter_pattern, text))
        
        if not chapter_matches:
            return [{
                'title': '第一章',
                'start_pos': 0,
                'end_pos': len(text)
            }]
        
        # 构建章节列表
        chapters = []
        for i, match in enumerate(chapter_matches):
            start_pos = match.start()
            # 如果是最后一个章节，结束位置为文本末尾
            end_pos = chapter_matches[i + 1].start() if i < len(chapter_matches) - 1 else len(text)
            
            # 获取匹配的章节标题
            chapter_title = match.group()
            # 移除可能的多余空白字符和换行符
            chapter_title = chapter_title.strip().replace('\n', ' ').replace('\r', '')
            # 移除多余的空格
            chapter_title = re.sub(r'\s+', ' ', chapter_title)
            
            chapters.append({
                'title': chapter_title,
                'start_pos': start_pos,
                'end_pos': end_pos
            })
        
        # 打印章节信息
        print("\n识别到的章节：")
        for i, chapter in enumerate(chapters, 1):
            print(f"{i}. {chapter['title']} (位置: {chapter['start_pos']}-{chapter['end_pos']})")
        
        return chapters

    def extract_scene_detail(self, scenes_data):
        detailed_scenes = {}
        detailed_scenes["scenes"] = []
        for scene in scenes_data["scenes"]:
            start_str = scene["start_str"]
            scene_text = scene["context"]
            prompt = f"""
            Here is an excerpt from a novel, primarily a description of a single scene. Please analyze this scene.

            For this scene, please provide:
            1.  A summarized scene title
            2.  The time the scene occurs
            3.  The location where the scene takes place
            4.  All characters involved in the scene
            5.  A brief description of the scene

            Please return the information in JSON format, as follows:
            {{
                "name": "Scene Title",
                "time": "Actual time of the scene (if available)",
                "location": "Scene Location",
                "participants": ["Participant 1", "Participant 2"],
                "description": "Scene Description"
            }}

            Novel text excerpt:
            {scene_text}
            """

            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a professional novel analysis assistant, skilled in extracting and analyzing events within novels. Please ensure that the returned data is in correct JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={ "type": "json_object" }
            )
                
            
            detailed_scene = json.loads(response.choices[0].message.content)
            detailed_scene["start_str"] = start_str
            detailed_scene["context"] = scene_text
            detailed_scene["participants"] = self.standardize_participants(detailed_scene["participants"])
            detailed_scenes["scenes"].append(detailed_scene)
        
            
        return detailed_scenes

    def scene_base_split(self, chapters):
        print("正在识别章节...")
        print(f"识别到 {len(chapters)} 个章节")

        all_scenes = {}
        all_scenes["chapter_num"] = len(chapters)
        all_scenes["all_scenes"] = []
        
        scene_id = 1  # 事件ID计数器

        up_content = ""
        for i in range(len(chapters)):
            # 对每个章节进行处理
            print(f"处理第{i}章")
            chapter_text = up_content + chapters[i]["text"]

            
            prompt = f"""
            lease analyze the following novel text excerpt and extract all scenes. The criteria for distinguishing different scenes are:
            1.  Whether the characters in the scene change
            2.  Whether important events occur to the characters in the scene
            3.  Whether important conversations occur between the characters in the scene
            4.  Whether important actions are taken by the characters in the scene
            5.  Whether the scene location changes

            For each scene, please return the original text:
            1.  The beginning characters of the scene. If it's the first scene, it must be the very beginning of the excerpt.

            Requirements:
            1. Each scene must be arranged in the same order as the original narrative.
            2. Ensure punctuation marks exactly match the original text.
            3. Avoid excessive segmentation, but guarantee no omissions.

            Please return the information in JSON format, as follows:
            {{
                "scenes": [
                    {{
                        "str_start": "A single sentence from the original text at the beginning of the scene, ensuring correct punctuation and spacing."
                    }}
                ]
            }}

            Novel text excerpt:
            {chapter_text}
            """

            response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a professional novel analysis assistant, skilled in extracting and analyzing events within novels. Please ensure that the returned data is in correct JSON format."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    response_format={ "type": "json_object" }
                )
            
            chunk_scenes = json.loads(response.choices[0].message.content)
            print("已生成场景开头")
            chunk_scenes = self.extract_context(chapter_text, chunk_scenes)
            print("已成功分割场景")
            up_content = chunk_scenes["scenes"][-1]["context"]
            chunk_scenes["scenes"].pop()
            detailed_scenes = self.extract_scene_detail(chunk_scenes)
            detailed_scenes["chapter"] = i + 1
            detailed_scenes["scene_num"] = len(detailed_scenes["scenes"])
            print("已为场景添加细节")

            all_scenes["all_scenes"].append(detailed_scenes)
            print(f"第{i}章处理完成")
            
            # 每处理完一章就保存一次角色别名字典
            self.save_character_aliases(self.dir)
            


        return all_scenes

        
    def extract_context(self, full_text, scenes_data):
        extracted_scenes = {"scenes": []}

        for i, scene in enumerate(scenes_data["scenes"]):
            start_str = scene["str_start"]
            print(start_str)
            start_index = full_text.find(start_str)
            while start_index == -1:
                prompt = f"""
                Analyze the provided novel text excerpt and identify sentences that are **subtly similar** to `{start_str}`. Return these identified sentences in their original form.

                Novel text excerpt:
                {full_text}
                """
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                )
                start_str = response.choices[0].message.content
                start_index = full_text.find(start_str)
                print("1")

            
            # 找到下一个场景的开头作为当前场景的结尾
            next_start_index = len(full_text)
            next_scene = scenes_data["scenes"][i + 1] if i + 1 < len(scenes_data["scenes"]) else None
            
            if next_scene:
                next_start_str = next_scene["str_start"]
                next_start_index = full_text.find(next_start_str, start_index + len(start_str))
                if next_start_index == -1:
                    next_start_index = len(full_text)
            
            # 提取场景文本
            scene_text = full_text[start_index:next_start_index].strip()
            extracted_scenes["scenes"].append({
                "start_str": start_str,
                "context": scene_text
            })
            
    
        return extracted_scenes

    

    def standardize_character_name(self, name):
        """标准化角色名称"""
        for standard_name, aliases in self.character_aliases.items():
            if name in aliases:
                return standard_name
        return name

    def standardize_participants(self, participants):
        """Standardize event participants list and maintain character aliases dictionary"""
        standardized_participants = []
        
        # Define list of generic role keywords
        generic_roles = [
            "passerby", "citizen", "crowd", "soldier", "guard", "servant", "eunuch", "maid", "minister", "official",
            "merchant", "farmer", "worker", "student", "teacher", "doctor", "patient", "elder", "child", "youth",
            "man", "woman", "boy", "girl", "old man", "old woman", "lady", "gentleman", "young master", "young lady",
            "servant", "maid", "attendant", "subordinate", "colleague", "friend", "enemy", "opponent", "companion",
            "people", "person", "individual", "someone", "anyone", "everyone", "nobody", "stranger", "visitor",
            "guest", "host", "leader", "follower", "member", "group", "team", "crew", "staff", "employee",
            "waiter", "waitress", "bartender", "driver", "pilot", "captain", "sailor", "soldier", "officer",
            "policeman", "policewoman", "detective", "investigator", "reporter", "journalist", "writer", "author",
            "artist", "musician", "actor", "actress", "director", "producer", "manager", "boss", "owner"
        ]
        
        for participant in participants:
            # Check if it's a generic role
            is_generic = False
            for generic in generic_roles:
                if generic.lower() in participant.lower():
                    is_generic = True
                    break
            
            if is_generic:
                standardized_participants.append(participant)
                continue
                
            # Check if already exists in aliases dictionary
            found = False
            for standard_name, aliases in self.character_aliases.items():
                if participant in aliases:
                    standardized_participants.append(standard_name)
                    found = True
                    break
            
            if not found:
                # Use API to identify character aliases
                prompt = f"""
                Please analyze the following character name and determine if it is an alias of a known character.
                If it is an alias of a known character, return the standard name.
                If it is a new character, return the original name.
                
                Note:
                1. Only process characters with specific names, do not process generic roles (like "passerby", "soldier", "citizen", etc.)
                2. If the input is a generic role, set is_generic to true
                3. For English novels, focus on characters with proper names (e.g., "John Smith", "Mr. Wilson")
                4. Consider titles and honorifics as part of the character's name (e.g., "Mr.", "Mrs.", "Dr.", "Sir")

                Known characters and their aliases:
                {json.dumps(self.character_aliases, ensure_ascii=False, indent=2)}

                Character name: {participant}

                Please return in JSON format as follows:
                {{
                    "is_generic": true/false,
                    "is_alias": true/false,
                    "standard_name": "standard name",
                    "aliases": ["alias1", "alias2", ...]
                }}
                """
                
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a professional novel analysis assistant, skilled in identifying and analyzing characters and their aliases. Please ensure to only process characters with specific names."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        response_format={ "type": "json_object" }
                    )
                    
                    result = json.loads(response.choices[0].message.content)
                    
                    if result["is_generic"]:
                        standardized_participants.append(participant)
                    elif result["is_alias"]:
                        # Update aliases dictionary
                        standard_name = result["standard_name"]
                        if standard_name not in self.character_aliases:
                            self.character_aliases[standard_name] = []
                        # Add new aliases
                        for alias in result["aliases"]:
                            if alias not in self.character_aliases[standard_name]:
                                self.character_aliases[standard_name].append(alias)
                        standardized_participants.append(standard_name)
                    else:
                        # Add as new character to dictionary
                        self.character_aliases[participant] = [participant]
                        standardized_participants.append(participant)
                        
                except Exception as e:
                    print(f"Error processing character {participant}: {str(e)}")
                    standardized_participants.append(participant)
        
        return standardized_participants

    def save_to_json(self, data, output_file):
        """保存结果到JSON文件"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"结果已保存到: {output_file}")
        except Exception as e:
            print(f"保存文件时出错: {str(e)}")

    def save_character_aliases(self, output_dir):
        """保存角色别名字典到JSON文件"""
        try:
            output_file = os.path.join(output_dir, "character_aliases.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.character_aliases, f, ensure_ascii=False, indent=4)
            print(f"角色别名字典已保存到: {output_file}")
        except Exception as e:
            print(f"保存角色别名字典时出错: {str(e)}")
            
    def load_character_aliases(self, input_dir):
        """从JSON文件加载角色别名字典"""
        try:
            input_file = os.path.join(input_dir, "character_aliases.json")
            if os.path.exists(input_file):
                with open(input_file, 'r', encoding='utf-8') as f:
                    self.character_aliases = json.load(f)
                print(f"已加载角色别名字典，包含 {len(self.character_aliases)} 个角色")
            else:
                print("未找到角色别名字典文件，将使用空字典")
        except Exception as e:
            print(f"加载角色别名字典时出错: {str(e)}")

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='小说场景提取工具')
    parser.add_argument('novel_name', type=str, help='小说名称（例如：The Great Gatsby）')
    args = parser.parse_args()

    # 创建实例
    processor = NovelCharacterEvents()
    
    # 根据小说名称生成文件名和目录名
    novel_name = args.novel_name
    input_file = f"{novel_name}_3000.json"
    dir = os.path.join("books", novel_name)
    


    # 读取小说
    print(f"正在读取小说{novel_name}文件...")
    chapters = processor.read_novel(input_file, dir)
    if not chapters:
        return

    
    all_scenes = processor.scene_base_split(chapters)
    if all_scenes:
        all_events_file = os.path.join(dir, f"all_events_{novel_name}.json")
        processor.save_to_json(all_scenes, all_events_file)
        print(f"所有事件已保存到: {all_events_file}")

    
    
if __name__ == "__main__":
    main() 