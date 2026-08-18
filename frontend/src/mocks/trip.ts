import type {
  Activity,
  DayPlan,
  TripPlanRequest,
  TripPlanResponse,
} from "../types/trip";

type DayTemplate = Omit<DayPlan, "day_index" | "trip_date" | "daily_cost">;

const DAY_TEMPLATES: DayTemplate[] = [
  {
    weather_condition: "晴朗",
    weather_kind: "sunny",
    weather_high: 24,
    weather_low: 16,
    day_note: "第一天把脚步放慢，从湖边开始认识大理。",
    activities: [
      {
        name: "洱海环湖骑行",
        activity_type: "户外",
        period: "上午",
        start_time: "09:30",
        duration_min: 150,
        description: "沿着生态廊道骑行，遇见开阔湖面与远处苍山。",
        estimated_cost: 280,
        location: "洱海生态廊道",
        weather_note: "天气晴朗，适合骑行。",
        couple_note: "风从湖面来，我只想和你并肩慢一点。",
      },
      {
        name: "喜洲古镇漫步",
        activity_type: "文化",
        period: "上午",
        start_time: "12:00",
        duration_min: 90,
        description: "穿过白族民居，尝尝刚出炉的喜洲粑粑。",
        estimated_cost: 90,
        location: "喜洲古镇",
        couple_note: "青瓦白墙下，我们的影子也变温柔了。",
      },
      {
        name: "寂照庵素斋",
        activity_type: "美食",
        period: "下午",
        start_time: "12:30",
        duration_min: 80,
        description: "在花木环绕的庵堂里，吃一顿清淡素斋。",
        estimated_cost: 80,
        location: "感通寺附近",
        indoor_backup: "感通索道游客中心餐厅",
      },
      {
        name: "海西下午茶",
        activity_type: "室内",
        period: "下午",
        start_time: "15:30",
        duration_min: 90,
        description: "在看得见稻田的窗边，分享一份甜点和咖啡。",
        estimated_cost: 130,
        location: "海西田园咖啡",
        couple_note: "甜点分你一半，快乐就变成双份。",
      },
      {
        name: "双廊日落晚餐",
        activity_type: "美食",
        period: "晚间",
        start_time: "18:30",
        duration_min: 110,
        description: "临湖而坐，看天色从橘红慢慢沉入深蓝。",
        estimated_cost: 320,
        location: "双廊镇",
        couple_note: "落日沉进湖里，像把今天也酿成了酒。",
      },
    ],
  },
  {
    weather_condition: "多云",
    weather_kind: "cloudy",
    weather_high: 22,
    weather_low: 15,
    day_note: "云层柔软，适合上山也适合躲进一间小店。",
    activities: [
      {
        name: "苍山洗马潭索道",
        activity_type: "户外",
        period: "上午",
        start_time: "09:00",
        duration_min: 180,
        description: "乘索道缓缓上升，俯瞰大理坝子与洱海。",
        estimated_cost: 360,
        location: "苍山国家地质公园",
        weather_note: "山上风大，带一件薄外套。",
        indoor_backup: "苍山地质博物馆",
      },
      {
        name: "天龙八部影视城",
        activity_type: "文化",
        period: "上午",
        start_time: "12:00",
        duration_min: 100,
        description: "走进熟悉的江湖场景，拍一组有故事的照片。",
        estimated_cost: 120,
        location: "天龙八部影视城",
      },
      {
        name: "才村湿地散步",
        activity_type: "户外",
        period: "下午",
        start_time: "14:30",
        duration_min: 80,
        description: "沿着湿地栈道慢慢走，看白鹭从芦苇间飞起。",
        estimated_cost: 0,
        location: "才村码头",
        couple_note: "不说话也很好，风替我们交换了心情。",
      },
      {
        name: "白族火塘晚餐",
        activity_type: "美食",
        period: "晚间",
        start_time: "18:30",
        duration_min: 100,
        description: "围坐火塘，吃一顿暖呼呼的本地菜。",
        estimated_cost: 260,
        location: "大理古城",
      },
      {
        name: "古城民谣酒吧",
        activity_type: "室内",
        period: "晚间",
        start_time: "21:00",
        duration_min: 90,
        description: "点一杯低度果酒，听歌手唱今晚的故事。",
        estimated_cost: 180,
        location: "人民路",
        couple_note: "歌声落在耳边，像把夜色轻轻盖在我们身上。",
      },
    ],
  },
  {
    weather_condition: "小雨",
    weather_kind: "rainy",
    weather_high: 20,
    weather_low: 15,
    day_note: "雨天的节奏慢下来，适合手作和安静告别。",
    activities: [
      {
        name: "崇圣寺三塔",
        activity_type: "文化",
        period: "上午",
        start_time: "09:30",
        duration_min: 120,
        description: "在雨雾中看三塔，塔影与倒影都多了一层静谧。",
        estimated_cost: 150,
        location: "崇圣寺三塔文化旅游区",
        weather_note: "已切换为室内与遮雨动线。",
        indoor_backup: "崇圣寺文物陈列馆",
      },
      {
        name: "白族扎染体验",
        activity_type: "室内",
        period: "下午",
        start_time: "13:30",
        duration_min: 150,
        description: "亲手扎一块蓝白方巾，把大理的颜色带回家。",
        estimated_cost: 220,
        location: "周城扎染坊",
        couple_note: "同一块布，染进我们不同的期待。",
      },
      {
        name: "海舌公园",
        activity_type: "户外",
        period: "下午",
        start_time: "16:30",
        duration_min: 60,
        description: "如果雨停，就去湖边的沙洲走一小段。",
        estimated_cost: 0,
        location: "海舌生态公园",
        indoor_backup: "附近书店",
      },
      {
        name: "返程前咖啡馆",
        activity_type: "室内",
        period: "晚间",
        start_time: "17:30",
        duration_min: 70,
        description: "坐下来写一张明信片，把旅途收进句号里。",
        estimated_cost: 90,
        location: "大理古城",
        couple_note: "下次旅行还没开始，我已经开始期待。",
      },
    ],
  },
];

function addDays(date: string, amount: number): string {
  const parsed = new Date(`${date}T00:00:00`);
  parsed.setDate(parsed.getDate() + amount);
  return toIsoDate(parsed);
}

function toIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getDayCount(request: TripPlanRequest): number {
  const start = new Date(`${request.start_date}T00:00:00`).getTime();
  const end = new Date(`${request.end_date}T00:00:00`).getTime();

  if (Number.isNaN(start) || Number.isNaN(end)) {
    return 1;
  }

  return Math.min(DAY_TEMPLATES.length, Math.max(1, Math.round((end - start) / 86400000) + 1));
}

export function createMockPlan(request: TripPlanRequest): TripPlanResponse {
  const dayCount = getDayCount(request);
  const days: DayPlan[] = DAY_TEMPLATES.slice(0, dayCount).map(
    (template, index) => {
      const dailyCost = template.activities.reduce(
        (sum, activity) => sum + activity.estimated_cost,
        0,
      );

      return {
        ...template,
        day_index: index,
        trip_date: addDays(request.start_date, index),
        daily_cost: dailyCost,
      };
    },
  );

  const totalSpent = days.reduce((sum, day) => sum + day.daily_cost, 0);
  const overBudget = totalSpent > request.budget;

  return {
    plan_id: `mock-${Date.now()}`,
    destination: request.destination,
    start_date: request.start_date,
    end_date: request.end_date,
    budget_breakdown: {
      total_budget: request.budget,
      total_spent: totalSpent,
      by_day: days.map((day) => day.daily_cost),
      over_budget: overBudget,
      downgrade_applied: overBudget,
      downgrade_notes: overBudget
        ? ["已将晚间酒吧调整为预算内选择", "部分交通动线已改为步行"]
        : [],
    },
    days,
    couple_notes: [
      "好的旅行不是去很远的地方，而是和你一起，把普通的一天过得很慢。",
      "愿每一阵风、每一场雨，都成为我们故事里的注脚。",
    ],
    status: "completed",
  };
}

export const MOCK_PLAN = createMockPlan({
  origin: "北京",
  destination: "大理",
  start_date: "2026-09-01",
  end_date: "2026-09-03",
  budget: 4500,
  preferences: ["浪漫", "美食", "自然"],
  pace: "轻松",
});

export type { Activity };
