"""启动时自动初始化导览内容库（正式版——不再创建测试设备/识别/问答模拟数据）"""
from app.database import SessionLocal
from app.models import ScenicSpot


def seed_data():
    db = SessionLocal()
    try:
        # ---- 仅初始化导览内容库（景点知识） ----
        # 正式版不再自动插入模拟设备、识别记录、问答记录。
        # 设备由远程端通过 POST /api/devices/heartbeat 自动注册；
        # 识别记录由 POST /api/device/events 自动写入；
        # 问答记录由 POST /api/qa-records 自动写入。
        if db.query(ScenicSpot).count() == 0:
            spots = [
                ScenicSpot(
                    class_name="The Statue of Liberty",
                    display_name="自由女神像",
                    domain="scenic",
                    introduction="自由女神像是法国于1886年赠送给美国独立100周年的礼物，位于纽约港的自由岛上。",
                    history="由法国雕塑家弗雷德里克·奥古斯特·巴托尔迪设计，古斯塔夫·埃菲尔协助内部结构设计。",
                    features="铜像高46米，底座高47米，总高度93米。右手高举火炬，左手捧着独立宣言。",
                    narration="欢迎来到自由女神像！这座雄伟的雕像象征着自由与民主，是纽约乃至整个美国最著名的地标之一。",
                    image_url="",
                ),
                ScenicSpot(
                    class_name="Oriental Pearl Tower",
                    display_name="东方明珠塔",
                    domain="scenic",
                    introduction="东方明珠广播电视塔位于上海浦东新区陆家嘴，高468米，是上海的标志性建筑。",
                    history="1991年动工，1994年建成，曾是亚洲第一高塔。由上海现代建筑设计集团设计。",
                    features='由11个大小不一的球体串联而成，寓意"大珠小珠落玉盘"。有267米高的旋转餐厅和259米高的悬空观光廊。',
                    narration="您现在看到的是上海东方明珠塔！它矗立在黄浦江畔，见证着上海从工业城市到国际大都市的华丽转变。",
                    image_url="",
                ),
                ScenicSpot(
                    class_name="Sydney Opera House",
                    display_name="悉尼歌剧院",
                    domain="scenic",
                    introduction="悉尼歌剧院位于澳大利亚悉尼港，是20世纪最具代表性的建筑之一，2007年被列为世界文化遗产。",
                    history="由丹麦建筑师约恩·乌松设计，1959年动工，1973年正式开放，历时14年建成。",
                    features="独特的贝壳形屋顶结构，覆盖着超过100万片瑞典瓷砖。包含多个演出厅，最大的音乐厅可容纳2679人。",
                    narration="欢迎来到悉尼歌剧院！这座如白帆般的建筑是澳大利亚的象征，每年吸引数百万游客前来参观。",
                    image_url="",
                ),
                ScenicSpot(
                    class_name="The Sphinx",
                    display_name="狮身人面像",
                    domain="scenic",
                    introduction="狮身人面像位于埃及吉萨金字塔群旁，长约73米，高约20米，是古埃及最著名的雕塑之一。",
                    history="据考证建于公元前2500年左右，由法老哈夫拉下令建造。数千年来一直守护着吉萨高原。",
                    features="狮身代表力量，人面代表智慧。雕刻于整块石灰岩，面部据信是法老哈夫拉的肖像。",
                    narration="您面前的是神秘的狮身人面像！它已经守护金字塔超过4500年，见证着古埃及文明的辉煌。",
                    image_url="",
                ),
                ScenicSpot(
                    class_name="The Great Wall",
                    display_name="长城",
                    domain="scenic",
                    introduction="长城是中国古代最宏伟的防御工程，总长度超过21000公里，1987年被列为世界文化遗产。",
                    history="始建于春秋战国时期，秦朝统一后连接加固，明朝进行了最大规模的修建，历时2000余年。",
                    features="城墙平均高7-8米，宽4-5米。八达岭段是最具代表性的部分，依山势而建，蜿蜒起伏。",
                    narration="欢迎来到万里长城！它是中国古代劳动人民智慧的结晶，也是人类历史上最伟大的建筑工程之一。",
                    image_url="",
                ),
            ]
            db.add_all(spots)
            db.commit()

    finally:
        db.close()
