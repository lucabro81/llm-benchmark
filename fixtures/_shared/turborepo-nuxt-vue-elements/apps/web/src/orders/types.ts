export type OrderStatus = "pending" | "processing" | "shipped" | "delivered" | "cancelled";

export interface Order {
  id: string;
  customer: string;
  status: OrderStatus;
  items: number;
  total: number;
  date: string;
}

export interface OrderColumnHandlers {
  onView: (order: Order) => void;
  onCancel: (order: Order) => void;
}
