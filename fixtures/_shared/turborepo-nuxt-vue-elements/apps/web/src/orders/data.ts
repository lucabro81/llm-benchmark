import type { Order } from "./types";

export const orders: Order[] = [
  { id: "ORD001", customer: "Alice Martin", status: "delivered", items: 3, total: 124.99, date: "2024-11-15" },
  { id: "ORD002", customer: "Bob Chen", status: "processing", items: 1, total: 49.95, date: "2024-12-01" },
  { id: "ORD003", customer: "Clara Russo", status: "pending", items: 5, total: 349.00, date: "2024-12-10" },
  { id: "ORD004", customer: "David Kim", status: "shipped", items: 2, total: 89.50, date: "2024-12-08" },
  { id: "ORD005", customer: "Eva Fischer", status: "cancelled", items: 1, total: 19.99, date: "2024-11-28" },
  { id: "ORD006", customer: "Frank Lopez", status: "delivered", items: 4, total: 210.00, date: "2024-11-20" },
  { id: "ORD007", customer: "Grace Wang", status: "processing", items: 2, total: 67.80, date: "2024-12-05" },
  { id: "ORD008", customer: "Henry Müller", status: "pending", items: 6, total: 512.50, date: "2024-12-12" },
  { id: "ORD009", customer: "Isabel Santos", status: "shipped", items: 1, total: 34.99, date: "2024-12-09" },
  { id: "ORD010", customer: "Jack Turner", status: "delivered", items: 3, total: 155.00, date: "2024-11-25" },
  { id: "ORD011", customer: "Karim Diallo", status: "cancelled", items: 2, total: 98.40, date: "2024-11-30" },
  { id: "ORD012", customer: "Lena Novak", status: "processing", items: 1, total: 22.99, date: "2024-12-11" },
  { id: "ORD013", customer: "Marco Bianchi", status: "pending", items: 4, total: 279.60, date: "2024-12-13" },
  { id: "ORD014", customer: "Nadia Tremblay", status: "shipped", items: 2, total: 143.00, date: "2024-12-07" },
  { id: "ORD015", customer: "Omar Hassan", status: "delivered", items: 5, total: 398.75, date: "2024-11-18" },
];
