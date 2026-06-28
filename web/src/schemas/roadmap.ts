import { z } from "zod";

export const roadmapRequestSchema = z.object({
  goal: z.string().min(1, "Select what you want to obtain"),
  subCity: z.string().min(1, "Select your sub-city"),
  industry: z.string().optional(),
  documentsHeld: z.array(z.string()),
});

export type RoadmapRequestInput = z.infer<typeof roadmapRequestSchema>;
