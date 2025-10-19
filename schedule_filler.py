import csv
import re
import random
from datetime import time, datetime, timedelta, date
from collections import defaultdict

# --- 全局设定 (Global Settings) ---

# 1. 定义地点 (元组: "地点类型", "建筑序号")
DORMITORIES = [("宿舍", f"{i:03d}栋") for i in range(1, 101)]
CANTEENS = [("食堂", f"{i:02d}") for i in range(1, 11)]
LIBRARIES = [("图书馆", f"{i}") for i in range(1, 5)]

# 2. 设定一天的起止时间
DAY_START = time(7, 0, 0)
DAY_END = time(22, 0, 0)

# 3. 设定午餐和晚餐时间窗口
LUNCH_START = time(11, 30, 0)
LUNCH_END = time(13, 30, 0)
DINNER_START = time(17, 30, 0)
DINNER_END = time(19, 0, 0)


def parse_start_end_from_string(time_col_str: str) -> (time, time):
    """
    从原始第8列字符串中解析出开始和结束时间, e.g.,
    "104 [1900-01-01 08:00:00, 1900-01-01 09:35:00]"
    返回 (datetime.time, datetime.time)
    """
    matches = re.findall(r'(\d{2}:\d{2}:\d{2})', time_col_str)
    if len(matches) == 2:
        try:
            start_t = time.fromisoformat(matches[0])
            end_t = time.fromisoformat(matches[1])
            return start_t, end_t
        except ValueError:
            return None, None
    return None, None


def format_time_range(start_t: time, end_t: time) -> str:
    """
    将 datetime.time 对象格式化回新行所需的字符串
    e.g., "[1900-01-01 08:00:00, 1900-01-01 09:35:00]"
    """
    base_date = "1900-01-01"
    start_str = f"{base_date} {start_t.isoformat()}"
    end_str = f"{base_date} {end_t.isoformat()}"
    return f"[{start_str}, {end_str}]"


def load_schedule(csv_file: str) -> (list, dict):
    schedules = defaultdict(list)
    header = []
    try:
        with open(csv_file, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)
            print(f"CSV表头共有 {len(header)} 列")
            
            for row in reader:
                if len(row) < len(header):
                    print(f"警告: 跳过不完整的行 (应有{len(header)}列): {row}")
                    continue

                day = row[1] if len(row) > 1 else ""
                # 时间列应该是最后一列
                time_col_str = row[-1]
                start_t, end_t = parse_start_end_from_string(time_col_str)

                if day and start_t and end_t:
                    schedules[day].append((start_t, end_t, row))

    except FileNotFoundError:
        print(f"错误: 找不到文件 {csv_file}")
        return [], {}
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return [], {}

    for day in schedules:
        schedules[day].sort(key=lambda x: x[0])

    return header, schedules


def print_free_slots(day_name: str, classes: list):
    """打印某一天的空闲时间段"""
    current_time = DAY_START
    free_slots = []

    for start_t, end_t, _ in classes:
        if start_t > current_time:
            free_slots.append((current_time, start_t))
        # 确保 current_time 总是向前推进
        if end_t > current_time:
            current_time = end_t

    if current_time < DAY_END:
        free_slots.append((current_time, DAY_END))

    print(f"\n{day_name} 的空闲时间段：")
    for start, end in free_slots:
        print(f"  从 {start} 到 {end}")
    return free_slots


def fill_free_time(day_name: str, free_slots: list, home_dorm: tuple, header_length: int) -> list:
    """
    填充空闲时间段，返回新事件行列表
    header_length: CSV表头的列数，用于确保新行列数一致
    """
    filled_events = []

    def create_new_row(activity_name: str, loc_tuple: tuple, start_t: time, end_t: time) -> list:
        loc_type, loc_name = loc_tuple
        time_str = format_time_range(start_t, end_t)
        
        # 创建与原始CSV列数相同的行
        # 假设格式为: [活动名, 星期, -, -, -, -, 地点类型, 地点名称, 时间字符串]
        # 如果原始CSV有更多列，则用"-"填充
        event = [
            activity_name,
            day_name,
            "-",
            "-",
            "-",
            "-",
            loc_type,
            loc_name,
            time_str
        ]
        
        # 如果表头列数大于9，补齐到相同长度
        while len(event) < header_length:
            event.append("-")
        
        # 如果表头列数小于9，截断到相同长度
        event = event[:header_length]
        
        print(f"  插入事件: {event[0]}, {event[1]}, {event[6]}, {event[7]}, {start_t}-{end_t}")
        return event

    if not free_slots:
        return []

    # --- 1. 处理早上的第一个空闲时段 (起床) ---
    first_slot_start, first_slot_end = free_slots[0]
    filled_events.append(create_new_row(
        "起床/准备/早餐", home_dorm, first_slot_start, first_slot_end
    ))

    # --- 2. 处理中间的空闲时段 (自习/午餐) ---
    ate_lunch = False
    # 跳过第一个 (早餐) 和最后一个 (晚餐/休息)
    for start, end in free_slots[1:-1] if len(free_slots) > 2 else []:
        lunch_overlap_start = max(start, LUNCH_START)
        lunch_overlap_end = min(end, LUNCH_END)
        current_time = start

        if not ate_lunch and (lunch_overlap_start < lunch_overlap_end):
            # 午餐前的时间
            if current_time < lunch_overlap_start:
                filled_events.append(create_new_row(
                    "自习", random.choice(LIBRARIES), current_time, lunch_overlap_start
                ))

            # 计算午餐时间 (最多1小时)
            lunch_duration = (datetime.combine(date.min, lunch_overlap_end) - datetime.combine(date.min,
                                                                                                lunch_overlap_start)).total_seconds()
            actual_lunch_duration = min(lunch_duration, 3600)
            actual_lunch_end_time = (datetime.combine(date.min, lunch_overlap_start) + timedelta(
                seconds=actual_lunch_duration)).time()

            filled_events.append(create_new_row(
                "午餐", random.choice(CANTEENS), lunch_overlap_start, actual_lunch_end_time
            ))

            ate_lunch = True
            current_time = actual_lunch_end_time

        # 剩下的时间 (如果还有)
        if current_time < end:
            filled_events.append(create_new_row(
                "自习", random.choice(LIBRARIES), current_time, end
            ))

    # --- 3. 处理最后一个空闲时段 (晚餐/回宿舍) ---
    if len(free_slots) > 1:
        last_slot_start, last_slot_end = free_slots[-1]
        dinner_overlap_start = max(last_slot_start, DINNER_START)
        dinner_overlap_end = min(last_slot_end, DINNER_END)
        current_time = last_slot_start

        if dinner_overlap_start < dinner_overlap_end:
            # 晚餐前的时间
            if current_time < dinner_overlap_start:
                filled_events.append(create_new_row(
                    "自习", random.choice(LIBRARIES), current_time, dinner_overlap_start
                ))

            # 计算晚餐时间 (最多1小时)
            dinner_duration = (datetime.combine(date.min, dinner_overlap_end) - datetime.combine(date.min,
                                                                                                  dinner_overlap_start)).total_seconds()
            actual_dinner_duration = min(dinner_duration, 3600)
            actual_dinner_end_time = (datetime.combine(date.min, dinner_overlap_start) + timedelta(
                seconds=actual_dinner_duration)).time()

            filled_events.append(create_new_row(
                "晚餐", random.choice(CANTEENS), dinner_overlap_start, actual_dinner_end_time
            ))
            current_time = actual_dinner_end_time

        # 晚餐后的时间
        if current_time < last_slot_end:
            filled_events.append(create_new_row(
                "晚上休息/回宿舍", home_dorm, current_time, last_slot_end
            ))
    elif len(free_slots) == 1:
        # 如果只有一个空闲时段（整天都空闲）
        slot_start, slot_end = free_slots[0]
        filled_events.append(create_new_row(
            "休息/自由活动", home_dorm, slot_start, slot_end
        ))

    return filled_events


def main():
    # !! 请确保路径正确 !!
    INPUT_CSV = '/Users/dongxingao/Downloads/cleaned_class_data_include_time.csv'
    OUTPUT_CSV = '/Users/dongxingao/Downloads/cleaned_class_data_include_time_with_random.csv'

    header, schedules = load_schedule(INPUT_CSV)
    if not schedules:
        print("未加载任何课程，程序退出。")
        return

    print(f"\n成功从 {INPUT_CSV} 加载 {len(schedules)} 天的课程。")

    all_events_to_write = []
    # 星期一=1, 星期日=7
    day_map = {"星期1": 1, "星期2": 2, "星期3": 3, "星期4": 4, "星期5": 5, "星期6": 6, "星期7": 7}

    for day in sorted(schedules.keys(), key=lambda d: day_map.get(d, 8)):
        classes = schedules[day]
        home_dorm = random.choice(DORMITORIES)

        print(f"\n处理 {day}:")
        print(f"  原始课程数: {len(classes)}")
        
        # 先把当天的原始课程加回列表
        for _, _, original_row in classes:
            all_events_to_write.append(original_row)

        # 打印空闲时间段
        free_slots = print_free_slots(day, classes)

        # 生成填充事件
        if free_slots:
            filled_event_rows = fill_free_time(day, free_slots, home_dorm, len(header))
            print(f"  新增事件数: {len(filled_event_rows)}")
            all_events_to_write.extend(filled_event_rows)

    # 按星期和时间排序
    def get_sort_key(row):
        day_key = day_map.get(row[1], 8) if len(row) > 1 else 8
        # 时间列是最后一列
        start_t, _ = parse_start_end_from_string(row[-1]) if len(row) > 0 else (None, None)
        if start_t:
            return (day_key, start_t)
        return (day_key, time(0, 0, 0))  # 无法解析则排在最前

    all_events_to_write.sort(key=get_sort_key)

    print(f"\n总共生成 {len(all_events_to_write)} 条记录")

    # 将最终结果写入新CSV文件
    try:
        with open(OUTPUT_CSV, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(header)  # 写入表头
            for row_data in all_events_to_write:
                writer.writerow(row_data)  # 写入每一行

        print(f"\n✓ 成功！完整的日程表已保存到: {OUTPUT_CSV}")

    except Exception as e:
        print(f"\n✗ 写入文件时发生错误: {e}")


# --- 运行脚本 ---
if __name__ == "__main__":
    main()
