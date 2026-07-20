import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  requireSession: vi.fn(),
  revalidatePath: vi.fn(),
  updateUser: vi.fn(),
}));

vi.mock("@meddoc/db", () => ({
  default: { user: { update: mocks.updateUser } },
}));
vi.mock("@/lib/auth", () => ({ requireSession: mocks.requireSession }));
vi.mock("next/cache", () => ({ revalidatePath: mocks.revalidatePath }));

import { updateProfileAction } from "../profile";

const syntheticDsn =
  "postgresql://synthetic_profile_user:synthetic_profile_password@db.synthetic.invalid/profile_test";
const syntheticName = "Synthetic Profile Input Marker";
const syntheticClinic = "Synthetic Clinic Input Marker";
const syntheticNpi = "1234567890";

function profileForm(): FormData {
  const form = new FormData();
  form.set("name", syntheticName);
  form.set("specialty", "unspecified");
  form.set("npi", syntheticNpi);
  form.set("clinicName", syntheticClinic);
  form.set("timeZone", "Etc/UTC");
  return form;
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.requireSession.mockResolvedValue({
    user: { id: "synthetic-profile-user" },
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("profile update error logging", () => {
  it("emits only a fixed diagnostic when persistence rejects", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    mocks.updateUser.mockRejectedValueOnce(
      new Error(
        `${syntheticDsn} rejected profile name=${syntheticName} clinic=${syntheticClinic} npi=${syntheticNpi}`,
      ),
    );

    await expect(updateProfileAction(null, profileForm())).resolves.toEqual({
      ok: false,
      errors: { _form: "Could not save. Try again." },
    });

    expect(consoleError).toHaveBeenCalledTimes(1);
    expect(consoleError).toHaveBeenCalledWith("[profile] update failed");
    const serializedCalls = JSON.stringify(consoleError.mock.calls);
    for (const forbidden of [
      syntheticDsn,
      "synthetic_profile_password",
      syntheticName,
      syntheticClinic,
      syntheticNpi,
    ]) {
      expect(serializedCalls).not.toContain(forbidden);
    }
    expect(mocks.revalidatePath).not.toHaveBeenCalled();
  });
});
