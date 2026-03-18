import { getBuylist, getStaples, getFlex } from "@/app/lib/data";
import { BuylistClient } from "./buylist-client";

export default function BuylistPage() {
  const buylist = getBuylist();
  const staples = getStaples();
  const flex = getFlex();
  return <BuylistClient buylist={buylist} staples={staples} flex={flex} />;
}
