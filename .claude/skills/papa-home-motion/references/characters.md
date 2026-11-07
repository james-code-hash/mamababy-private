<!-- 由 papa_home/skill_docs.py 從 assets/papa_home/motion/*.json 與 rig.json 產生；不要手改，改資料後跑 `python main.py papa motion-docs` -->


# 角色、姿勢與表情（rig.json）

物種骨架（assets/papa_home/motion/species.json）：動作只認零件角色（role），每個姿勢有哪些 role 決定能做哪些動作。

| role | 意思 |
|---|---|
| `body` | 整隻角色的容器（身體＋四肢＋頭一起動；跳、傾身、壓扁用這個） |
| `head` | 頭（含姿勢表情頭；轉頭、點頭、乾嘔用這個） |
| `arm_a` | 第一隻手／前腳（rig part front） |
| `arm_b` | 第二隻手／前腳（rig part front2；有些姿勢沒有，例如蹲著、抱寶寶） |
| `arm_lead` | 朝動作方向的那隻手：方向向右用 arm_b，向左用 arm_a，缺的那隻就用另一隻 |
| `legs` | 後腳／腿（rig part hind，目前只跟著身體動） |
| `tail` | 尾巴（rig 的 tail 圖，有 tail_pivot） |
| `lids` | 眼皮或眨眼貼片（頭像鏡與有表情的頭才有） |

## 大人（兩腳）（`human`）：dad、mom

不畫臉：沒有表情、嘴、眼皮，演戲全靠頭、手、身體；mood／mouth／eyes 不能寫。

### 爸爸（不畫臉）（`dad`）

不畫臉：沒有頭像鏡，cast 不能寫 mood／mood_to／eyes／mouth。

| 姿勢 | 內建表情 | 場景裡可換的表情（mood／mood_to） | 有的零件 | 能做的 gesture |
|---|---|---|---|---|
| `stand` | — | — | arm_a/arm_b/arm_lead/body/head/legs | shrug、reach、lean、gag、sniff、nod、shake、wave、tilt、startle、sigh |
| `crouch` | — | — | arm_a/arm_lead/body/head/legs | shrug、reach、lean、gag、sniff、nod、shake、wave、tilt、startle、sigh |
| `hold_baby` | — | — | arm_a/arm_lead/body/head/legs | shrug、reach、lean、gag、sniff、nod、shake、wave、tilt、startle、sigh |
| `flail` | — | — | arm_a/arm_b/arm_lead/body/head/legs | shrug、reach、lean、gag、sniff、nod、shake、wave、tilt、startle、sigh |
| `shrug` | — | — | arm_a/arm_b/arm_lead/body/head/legs | shrug、reach、lean、gag、sniff、nod、shake、wave、tilt、startle、sigh |

### 媽媽（不畫臉）（`mom`）

不畫臉：沒有頭像鏡，cast 不能寫 mood／mood_to／eyes／mouth。

| 姿勢 | 內建表情 | 場景裡可換的表情（mood／mood_to） | 有的零件 | 能做的 gesture |
|---|---|---|---|---|
| `stand` | — | — | arm_a/arm_b/arm_lead/body/head/legs | shrug、reach、lean、gag、sniff、nod、shake、wave、tilt、startle、sigh |
| `crouch` | — | — | arm_a/arm_lead/body/head/legs | shrug、reach、lean、gag、sniff、nod、shake、wave、tilt、startle、sigh |
| `hold_baby` | — | — | arm_a/arm_b/arm_lead/body/head/legs | shrug、reach、lean、gag、sniff、nod、shake、wave、tilt、startle、sigh |
| `explain` | — | — | arm_a/arm_b/arm_lead/body/head/legs | shrug、reach、lean、gag、sniff、nod、shake、wave、tilt、startle、sigh |

## 四腳（貓、狗）（`quadruped`）：papa、beibei

前腳當手用（聳肩、指、伸手都抬前腳）；每個姿勢能換的表情不一樣（貝貝 hide 頭埋著，完全不能換臉），看 characters.md。

### 帕帕（橘貓，唯一說話的角色）（`papa`）

頭像（CU／REACTION 的 head.expr）：`neutral`、`unimpressed`、`surprised`、`smug`、`soft`；閉眼＝`soft`

| 姿勢 | 內建表情 | 場景裡可換的表情（mood／mood_to） | 有的零件 | 能做的 gesture |
|---|---|---|---|---|
| `sit` | neutral | neutral、smug、soft、surprised、unimpressed | arm_a/arm_b/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |
| `stand` | smug | neutral、smug、soft、surprised、unimpressed | arm_a/arm_b/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |
| `lie` | unimpressed | neutral、smug、soft、surprised、unimpressed | arm_a/arm_b/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |
| `sign` | neutral | neutral、smug、soft、surprised、unimpressed | arm_a/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |
| `walk` | neutral | neutral、smug、soft、surprised、unimpressed | arm_a/arm_b/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |

### 貝貝（狗）（`beibei`）

頭像（CU／REACTION 的 head.expr）：`happy`、`innocent`、`scared`、`excited`、`furry`；閉眼＝`happy`

| 姿勢 | 內建表情 | 場景裡可換的表情（mood／mood_to） | 有的零件 | 能做的 gesture |
|---|---|---|---|---|
| `sit` | happy | excited、happy、innocent、scared | arm_a/arm_b/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |
| `stand` | innocent | excited、happy、innocent、scared | arm_a/arm_b/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |
| `run` | excited | excited、happy、innocent、scared | arm_a/arm_b/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |
| `hide` | scared | scared | arm_a/arm_b/arm_lead/body/head/legs/tail | wag_fast |
| `carry` | innocent | excited、happy、innocent、scared | arm_a/arm_b/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |
| `carry_fur` | innocent | excited、happy、innocent、scared | arm_a/arm_b/arm_lead/body/head/legs/tail | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh、wag_fast |
| `dive` | excited | excited、happy、innocent、scared | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |
| `furry` | happy | excited、happy、innocent、scared | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |

## 小孩（兩腳、有臉）（`child`）：sister、brother

頭的平移只做 30%、手的旋轉只做一半（圓頭配短脖子，頭一平移就露縫；短袖手轉太開肩膀接縫會露出來）。姊姊、弟弟：正面或側面、有表情，不說話（只有帕帕說話）。手舉高、指東西都看得到（大人是背影才不能用 point／cheer）。

### 姊姊（國小）（`sister`）

頭像（CU／REACTION 的 head.expr）：`smile`、`happy`、`angry`、`surprised`、`sad`；閉眼＝`None`

| 姿勢 | 內建表情 | 場景裡可換的表情（mood／mood_to） | 有的零件 | 能做的 gesture |
|---|---|---|---|---|
| `stand` | smile | angry、happy、sad、smile、surprised | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |
| `sit` | smile | angry、happy、sad、smile、surprised | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |
| `walk` | smile | angry、happy、sad、smile、surprised | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |
| `crouch` | smile | angry、happy、sad、smile、surprised | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |

### 弟弟（2 歲）（`brother`）

頭像（CU／REACTION 的 head.expr）：`smile`、`laugh`、`angry`、`surprised`、`cry`；閉眼＝`laugh`

| 姿勢 | 內建表情 | 場景裡可換的表情（mood／mood_to） | 有的零件 | 能做的 gesture |
|---|---|---|---|---|
| `stand` | smile | angry、cry、laugh、smile、surprised | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |
| `sit` | smile | angry、cry、laugh、smile、surprised | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |
| `walk` | smile | angry、cry、laugh、smile、surprised | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |
| `crouch` | smile | angry、cry、laugh、smile、surprised | arm_a/arm_b/arm_lead/body/head/legs | shrug、point、reach、lean、gag、sniff、nod、shake、wave、cheer、tilt、startle、sigh |

## 場景站位（spot）

- `living`：`front_left`、`front_center`、`front_right`、`mid_mat`、`sofa`、`cat_tree`、`dog_bed`
- `nursery`：`front_center`、`rug`、`crib`、`armchair`、`changing_table`
- `kitchen`：`front_center`、`counter`、`pet_bowls`、`high_chair`、`table`

## 道具與手部特寫

手部特寫（hand.prop／split.prop）：`dad_comb`（爸爸拿自己的梳子（拿錯東西））、`mom_brush`（媽媽拿寵物梳梳毛）、`mom_bottle`（媽媽拿奶瓶）、`mom_gauze`（媽媽拿紗布巾）、`mom_spoon`（媽媽一手端小碗米糊、一手拿小湯匙只沾一點（慢慢來，正確））、`dad_spoon_heap`（爸爸湯匙堆滿好幾種顏色的泥（一次加太多，錯誤））、`dad_salt`（爸爸往寶寶的米糊撒鹽（加調味料，錯誤））、`dad_honey`（爸爸拿蜂蜜棒往寶寶的米糊滴蜂蜜（1 歲以下不行，錯誤））、`mom_kid_wash`（媽媽帶小孩洗手（摸完、梳完毛馬上洗手））

道具（props/，split／demo 用）：`comb_a_clean`、`comb_b_full`、`comb_c_released`、`comb_fur_clump`、`fur_pile`、`hairball`、`hand_comb_reach`、`hand_dad_vacuum`、`hand_mom_comb`、`hand_mom_comb_release`

音效（sfx）：`scratch`、`bark`、`giggle`、`gag`、`whimper`、`vacuum`、`brush`、`steps`、`click`、`pop`、`whoosh`、`purr`

畫面效果（fx）：`tufts`、`floor_tufts`、`near`、`lines`
