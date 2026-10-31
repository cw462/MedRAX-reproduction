# V11 完整调用与终态记录

[总索引](../README.md) · [机器清单](../trace-manifest.json)

每阶段保留 60 题终态；只有实际触发新调用的题包含 messages。原始可观测请求、响应、解析结果、补充观察、调用计数与用量均来自保存的 checkpoint。完整原始 assistant 回复可核对解析器遗漏，不能把模型断言当作人工影像真值。

图像 data URI 改为相对图片引用；若请求中的压缩/缩放图片与已公开原图字节不同，则单独保留实际请求图片。运行机器绝对路径被脱敏；记录本身未重生成、未重新评分。

| 阶段 | 题目 | 路由 | 消息文件 |
|---|---|---|---|
| S1 | [10569_8353800725393](S1/10569_8353800725393.json) | selector | messages.json |
| S1 | [11624_8353800763402](S1/11624_8353800763402.json) | selector | messages.json |
| S1 | [11801_8353800651620](S1/11801_8353800651620.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [11804_8353800651404](S1/11804_8353800651404.json) | p0_missing | 无新增调用，仅终态 |
| S1 | [11858_8353800664572](S1/11858_8353800664572.json) | selector | messages.json |
| S1 | [12255_8353800651353](S1/12255_8353800651353.json) | p0_missing | 无新增调用，仅终态 |
| S1 | [12721_8353800681884](S1/12721_8353800681884.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [1281_8353802281357](S1/1281_8353802281357.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [13154_8353800587826](S1/13154_8353800587826.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [13238_8353800603808](S1/13238_8353800603808.json) | selector | messages.json |
| S1 | [13698_8353800603937](S1/13698_8353800603937.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [13935_8353800618951](S1/13935_8353800618951.json) | selector | messages.json |
| S1 | [1461_8353802159822](S1/1461_8353802159822.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [14838_8353800529839](S1/14838_8353800529839.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [15189_8353800545058](S1/15189_8353800545058.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [15314_8353800558683](S1/15314_8353800558683.json) | selector | messages.json |
| S1 | [16037_8353800455673](S1/16037_8353800455673.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [16486_8353800471802](S1/16486_8353800471802.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [1653_8353802281156](S1/1653_8353802281156.json) | selector | messages.json |
| S1 | [16568_8353800483171](S1/16568_8353800483171.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [16663_8353800455763](S1/16663_8353800455763.json) | selector | messages.json |
| S1 | [1678_8353802279918](S1/1678_8353802279918.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [17132_8143559675802](S1/17132_8143559675802.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [17182_8143559676067](S1/17182_8143559676067.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [17362_8143559680136](S1/17362_8143559680136.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [17621_8143559684844](S1/17621_8143559684844.json) | selector | messages.json |
| S1 | [17947_8143559000377](S1/17947_8143559000377.json) | selector | messages.json |
| S1 | [18001_8143559000935](S1/18001_8143559000935.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [18202_8143559000122](S1/18202_8143559000122.json) | selector | messages.json |
| S1 | [18780_8143559008557](S1/18780_8143559008557.json) | selector | messages.json |
| S1 | [1975_8353802257622](S1/1975_8353802257622.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [2243_8353801511231](S1/2243_8353801511231.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [3241_8353801520855](S1/3241_8353801520855.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [3359_8353801515597](S1/3359_8353801515597.json) | selector | messages.json |
| S1 | [3397_8353801520783](S1/3397_8353801520783.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [3436_8353801521068](S1/3436_8353801521068.json) | selector | messages.json |
| S1 | [3546_8353801521080](S1/3546_8353801521080.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [3561_8353801511489](S1/3561_8353801511489.json) | selector | messages.json |
| S1 | [3686_8353801520174](S1/3686_8353801520174.json) | selector | messages.json |
| S1 | [3831_8353801520459](S1/3831_8353801520459.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [3834_8353801523222](S1/3834_8353801523222.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [4118_8353801523564](S1/4118_8353801523564.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [4491_8353801523228](S1/4491_8353801523228.json) | selector | messages.json |
| S1 | [4510_8353801532552](S1/4510_8353801532552.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [4734_8353801532720](S1/4734_8353801532720.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [528_8353802130481](S1/528_8353802130481.json) | selector | messages.json |
| S1 | [5369_8353801533158](S1/5369_8353801533158.json) | selector | messages.json |
| S1 | [548_8353802023456](S1/548_8353802023456.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [5533_8353801540251](S1/5533_8353801540251.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [562_8353802023537](S1/562_8353802023537.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [722_8353802117601](S1/722_8353802117601.json) | selector | messages.json |
| S1 | [7659_8353800871660](S1/7659_8353800871660.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [7726_8353800871273](S1/7726_8353800871273.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [7738_8353800850751](S1/7738_8353800850751.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [8129_8353800862240](S1/8129_8353800862240.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [8300_8353800861859](S1/8300_8353800861859.json) | selector | messages.json |
| S1 | [8379_8353800889338](S1/8379_8353800889338.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [8911_8353800871456](S1/8911_8353800871456.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [9308_8353800801854](S1/9308_8353800801854.json) | inherited_agreement | 无新增调用，仅终态 |
| S1 | [9815_8353800828253](S1/9815_8353800828253.json) | inherited_agreement | 无新增调用，仅终态 |
| S2 | [10569_8353800725393](S2/10569_8353800725393.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [11624_8353800763402](S2/11624_8353800763402.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [11801_8353800651620](S2/11801_8353800651620.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [11804_8353800651404](S2/11804_8353800651404.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [11858_8353800664572](S2/11858_8353800664572.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [12255_8353800651353](S2/12255_8353800651353.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [12721_8353800681884](S2/12721_8353800681884.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [1281_8353802281357](S2/1281_8353802281357.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [13154_8353800587826](S2/13154_8353800587826.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [13238_8353800603808](S2/13238_8353800603808.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [13698_8353800603937](S2/13698_8353800603937.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [13935_8353800618951](S2/13935_8353800618951.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [1461_8353802159822](S2/1461_8353802159822.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [14838_8353800529839](S2/14838_8353800529839.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [15189_8353800545058](S2/15189_8353800545058.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [15314_8353800558683](S2/15314_8353800558683.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [16037_8353800455673](S2/16037_8353800455673.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [16486_8353800471802](S2/16486_8353800471802.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [1653_8353802281156](S2/1653_8353802281156.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [16568_8353800483171](S2/16568_8353800483171.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [16663_8353800455763](S2/16663_8353800455763.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [1678_8353802279918](S2/1678_8353802279918.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [17132_8143559675802](S2/17132_8143559675802.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [17182_8143559676067](S2/17182_8143559676067.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [17362_8143559680136](S2/17362_8143559680136.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [17621_8143559684844](S2/17621_8143559684844.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [17947_8143559000377](S2/17947_8143559000377.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [18001_8143559000935](S2/18001_8143559000935.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [18202_8143559000122](S2/18202_8143559000122.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [18780_8143559008557](S2/18780_8143559008557.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [1975_8353802257622](S2/1975_8353802257622.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [2243_8353801511231](S2/2243_8353801511231.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [3241_8353801520855](S2/3241_8353801520855.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [3359_8353801515597](S2/3359_8353801515597.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [3397_8353801520783](S2/3397_8353801520783.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [3436_8353801521068](S2/3436_8353801521068.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [3546_8353801521080](S2/3546_8353801521080.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [3561_8353801511489](S2/3561_8353801511489.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [3686_8353801520174](S2/3686_8353801520174.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [3831_8353801520459](S2/3831_8353801520459.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [3834_8353801523222](S2/3834_8353801523222.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [4118_8353801523564](S2/4118_8353801523564.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [4491_8353801523228](S2/4491_8353801523228.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [4510_8353801532552](S2/4510_8353801532552.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [4734_8353801532720](S2/4734_8353801532720.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [528_8353802130481](S2/528_8353802130481.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [5369_8353801533158](S2/5369_8353801533158.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [548_8353802023456](S2/548_8353802023456.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [5533_8353801540251](S2/5533_8353801540251.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [562_8353802023537](S2/562_8353802023537.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [722_8353802117601](S2/722_8353802117601.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [7659_8353800871660](S2/7659_8353800871660.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [7726_8353800871273](S2/7726_8353800871273.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [7738_8353800850751](S2/7738_8353800850751.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [8129_8353800862240](S2/8129_8353800862240.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [8300_8353800861859](S2/8300_8353800861859.json) | targeted_followup | plan_messages.json, reader_messages.json, selector_messages.json |
| S2 | [8379_8353800889338](S2/8379_8353800889338.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [8911_8353800871456](S2/8911_8353800871456.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [9308_8353800801854](S2/9308_8353800801854.json) | inherited_s1 | 无新增调用，仅终态 |
| S2 | [9815_8353800828253](S2/9815_8353800828253.json) | inherited_s1 | 无新增调用，仅终态 |
| S3 | [10569_8353800725393](S3/10569_8353800725393.json) | selector | messages.json, reader_messages.json |
| S3 | [11624_8353800763402](S3/11624_8353800763402.json) | selector | messages.json, reader_messages.json |
| S3 | [11801_8353800651620](S3/11801_8353800651620.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [11804_8353800651404](S3/11804_8353800651404.json) | p0_missing | 无新增调用，仅终态 |
| S3 | [11858_8353800664572](S3/11858_8353800664572.json) | selector | messages.json, reader_messages.json |
| S3 | [12255_8353800651353](S3/12255_8353800651353.json) | p0_missing | 无新增调用，仅终态 |
| S3 | [12721_8353800681884](S3/12721_8353800681884.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [1281_8353802281357](S3/1281_8353802281357.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [13154_8353800587826](S3/13154_8353800587826.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [13238_8353800603808](S3/13238_8353800603808.json) | selector | messages.json, reader_messages.json |
| S3 | [13698_8353800603937](S3/13698_8353800603937.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [13935_8353800618951](S3/13935_8353800618951.json) | selector | messages.json, reader_messages.json |
| S3 | [1461_8353802159822](S3/1461_8353802159822.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [14838_8353800529839](S3/14838_8353800529839.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [15189_8353800545058](S3/15189_8353800545058.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [15314_8353800558683](S3/15314_8353800558683.json) | selector | messages.json, reader_messages.json |
| S3 | [16037_8353800455673](S3/16037_8353800455673.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [16486_8353800471802](S3/16486_8353800471802.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [1653_8353802281156](S3/1653_8353802281156.json) | selector | messages.json, reader_messages.json |
| S3 | [16568_8353800483171](S3/16568_8353800483171.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [16663_8353800455763](S3/16663_8353800455763.json) | selector | messages.json, reader_messages.json |
| S3 | [1678_8353802279918](S3/1678_8353802279918.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [17132_8143559675802](S3/17132_8143559675802.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [17182_8143559676067](S3/17182_8143559676067.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [17362_8143559680136](S3/17362_8143559680136.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [17621_8143559684844](S3/17621_8143559684844.json) | selector | messages.json, reader_messages.json |
| S3 | [17947_8143559000377](S3/17947_8143559000377.json) | selector | messages.json, reader_messages.json |
| S3 | [18001_8143559000935](S3/18001_8143559000935.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [18202_8143559000122](S3/18202_8143559000122.json) | selector | messages.json, reader_messages.json |
| S3 | [18780_8143559008557](S3/18780_8143559008557.json) | selector | messages.json, reader_messages.json |
| S3 | [1975_8353802257622](S3/1975_8353802257622.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [2243_8353801511231](S3/2243_8353801511231.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [3241_8353801520855](S3/3241_8353801520855.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [3359_8353801515597](S3/3359_8353801515597.json) | selector | messages.json, reader_messages.json |
| S3 | [3397_8353801520783](S3/3397_8353801520783.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [3436_8353801521068](S3/3436_8353801521068.json) | selector | messages.json, reader_messages.json |
| S3 | [3546_8353801521080](S3/3546_8353801521080.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [3561_8353801511489](S3/3561_8353801511489.json) | selector | messages.json, reader_messages.json |
| S3 | [3686_8353801520174](S3/3686_8353801520174.json) | selector | messages.json, reader_messages.json |
| S3 | [3831_8353801520459](S3/3831_8353801520459.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [3834_8353801523222](S3/3834_8353801523222.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [4118_8353801523564](S3/4118_8353801523564.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [4491_8353801523228](S3/4491_8353801523228.json) | selector | messages.json, reader_messages.json |
| S3 | [4510_8353801532552](S3/4510_8353801532552.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [4734_8353801532720](S3/4734_8353801532720.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [528_8353802130481](S3/528_8353802130481.json) | selector | messages.json, reader_messages.json |
| S3 | [5369_8353801533158](S3/5369_8353801533158.json) | selector | messages.json, reader_messages.json |
| S3 | [548_8353802023456](S3/548_8353802023456.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [5533_8353801540251](S3/5533_8353801540251.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [562_8353802023537](S3/562_8353802023537.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [722_8353802117601](S3/722_8353802117601.json) | selector | messages.json, reader_messages.json |
| S3 | [7659_8353800871660](S3/7659_8353800871660.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [7726_8353800871273](S3/7726_8353800871273.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [7738_8353800850751](S3/7738_8353800850751.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [8129_8353800862240](S3/8129_8353800862240.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [8300_8353800861859](S3/8300_8353800861859.json) | selector | messages.json, reader_messages.json |
| S3 | [8379_8353800889338](S3/8379_8353800889338.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [8911_8353800871456](S3/8911_8353800871456.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [9308_8353800801854](S3/9308_8353800801854.json) | inherited_agreement | 无新增调用，仅终态 |
| S3 | [9815_8353800828253](S3/9815_8353800828253.json) | inherited_agreement | 无新增调用，仅终态 |
