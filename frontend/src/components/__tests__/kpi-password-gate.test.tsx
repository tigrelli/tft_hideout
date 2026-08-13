import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KpiPasswordGate } from "@/components/kpi/kpi-password-gate";

// WBS FE-12 테스트 요구사항: 비밀번호 게이트 컴포넌트 성공/실패 케이스.
describe("KpiPasswordGate", () => {
  it("비밀번호를 입력하고 제출하면 onSubmit이 입력값과 함께 호출된다", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <KpiPasswordGate
        onSubmit={onSubmit}
        errorMessage={null}
        isSubmitting={false}
      />,
    );

    await user.type(screen.getByLabelText("비밀번호"), "correct-pw");
    await user.click(screen.getByRole("button", { name: "확인" }));

    expect(onSubmit).toHaveBeenCalledWith("correct-pw");
  });

  it("errorMessage가 있으면 오답 안내 문구를 보여준다", () => {
    render(
      <KpiPasswordGate
        onSubmit={vi.fn()}
        errorMessage="비밀번호가 올바르지 않습니다."
        isSubmitting={false}
      />,
    );

    expect(
      screen.getByText("비밀번호가 올바르지 않습니다."),
    ).toBeInTheDocument();
  });

  it("isSubmitting이면 제출 버튼이 비활성화되고 진행 문구를 보여준다", () => {
    render(
      <KpiPasswordGate
        onSubmit={vi.fn()}
        errorMessage={null}
        isSubmitting={true}
      />,
    );

    expect(screen.getByRole("button", { name: "확인 중..." })).toBeDisabled();
  });
});
