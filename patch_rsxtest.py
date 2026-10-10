#!/usr/bin/env python3
"""Transform the upstream PSL1GHT RSX graphics sample into TF2 Fighter Prototype."""
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_rsxtest.py /path/to/PSL1GHT/samples/graphics/rsxtest")
root = Path(sys.argv[1])
main_cpp = root / "source" / "main.cpp"
makefile = root / "Makefile"
if not main_cpp.is_file() or not makefile.is_file():
    raise SystemExit(f"Expected PSL1GHT rsxtest source tree at: {root}")

source = main_cpp.read_text(encoding="utf-8")
marker = "void drawFrame()"
idx = source.find(marker)
if idx < 0:
    raise SystemExit("Could not find drawFrame() in upstream rsxtest; source layout changed.")

# Keep upstream RSX setup, mesh construction, shader initialization and exit callbacks.
game_code = r'''// ---- TF2 Fighter prototype code starts here ----

#include <math.h>

struct FighterInput {
    bool left, right, jump, melee, ranged, brutal, ultimate;
};

struct Shot {
    bool active;
    f32 x, y, vx, timer;
};

struct Fighter {
    f32 x, y, vx, vy, damage;
    f32 meleeCooldown, rangedCooldown, brutalTimer, brutalCooldown;
    f32 hitStun, attackTimer, invulnTimer, meter;
    int facing, stocks;
    bool onGround;
    bool oldJump, oldMelee, oldRanged, oldBrutal, oldUltimate;
    Shot shot;
};

static Fighter g_players[2];
static f32 g_trainOffset = 0.0f;
static f32 g_ultimateTimer = 0.0f;
static f32 g_ultimateBannerTimer = 0.0f;
static int g_ultimateAttacker = 0;
static int g_ultimateVictim = 1;
static int g_ultimateHitCount = 0;
static bool g_matchOver = false;
static int g_winner = 0;
static const f32 FLOOR_Y = -3.12f;

static SMeshBuffer *mFloor = NULL;
static SMeshBuffer *mTie = NULL;
static SMeshBuffer *mRail = NULL;
static SMeshBuffer *mWindow = NULL;
static SMeshBuffer *mBody = NULL;
static SMeshBuffer *mHead = NULL;
static SMeshBuffer *mArm = NULL;
static SMeshBuffer *mLeg = NULL;
static SMeshBuffer *mProjectile = NULL;
static SMeshBuffer *mBoundary = NULL;

static SMeshBuffer *makeBox(f32 sx, f32 sy, f32 sz)
{
    SMeshBuffer *m = createCube(1.0f);
    if (!m) return NULL;
    if (sx < 0.001f) sx = 0.001f;
    if (sy < 0.001f) sy = 0.001f;
    if (sz < 0.001f) sz = 0.001f;
    for (u32 i = 0; i < m->cnt_vertices; ++i) {
        m->vertices[i].pos = Vector3(m->vertices[i].pos.getX() * sx,
                                     m->vertices[i].pos.getY() * sy,
                                     m->vertices[i].pos.getZ() * sz);
        Vector3 n = m->vertices[i].nrm;
        m->vertices[i].nrm = normalize(Vector3(n.getX() / sx, n.getY() / sy, n.getZ() / sz));
    }
    return m;
}

static void resetFighter(Fighter *p, f32 x, int facing)
{
    memset(p, 0, sizeof(Fighter));
    p->x = x;
    p->y = FLOOR_Y;
    p->facing = facing;
    p->stocks = 3;
    p->onGround = true;
}

static FighterInput readInput(const padData *d, bool connected)
{
    FighterInput in;
    memset(&in, 0, sizeof(in));
    if (!connected || !d) return in;
    in.left = d->BTN_LEFT != 0;
    in.right = d->BTN_RIGHT != 0;
    in.jump = d->BTN_CROSS != 0;
    in.melee = d->BTN_SQUARE != 0;
    in.ranged = d->BTN_TRIANGLE != 0;
    in.brutal = d->BTN_R1 != 0;
    in.ultimate = d->BTN_CIRCLE != 0;
    return in;
}

static bool justPressed(bool down, bool *wasDown)
{
    bool result = down && !(*wasDown);
    *wasDown = down;
    return result;
}

static void drawMeshAt(SMeshBuffer *mesh, f32 x, f32 y, f32 z,
                       f32 red, f32 green, f32 blue)
{
    if (!mesh) return;
    u32 offset;
    Matrix4 viewMatrix, modelMatrix, modelMatrixIT, modelViewMatrix;
    Point3 lightPos = Point3(40.0f, 65.0f, 70.0f);
    Vector4 objEyePos, objLightPos;
    f32 globalAmbientColor[3] = {0.20f, 0.20f, 0.24f};
    f32 lightColor[3] = {0.95f, 0.95f, 0.95f};
    f32 materialColorDiffuse[3] = {red, green, blue};
    f32 materialColorSpecular[3] = {0.18f, 0.18f, 0.18f};
    f32 shininess = 7.0f;

    viewMatrix = Matrix4::lookAt(eye_pos, eye_dir, up_vec);
    modelMatrix = Matrix4::rotationX(0.0f) * Matrix4::rotationY(0.0f);
    modelMatrix.setTranslation(Vector3(x, y, z));
    modelMatrixIT = inverse(modelMatrix);
    modelViewMatrix = transpose(viewMatrix * modelMatrix);
    objEyePos = modelMatrixIT * eye_pos;
    objLightPos = modelMatrixIT * lightPos;

    rsxAddressToOffset(&mesh->vertices[0].pos, &offset);
    rsxBindVertexArrayAttrib(context, GCM_VERTEX_ATTRIB_POS, 0, offset,
        sizeof(S3DVertex), 3, GCM_VERTEX_DATA_TYPE_F32, GCM_LOCATION_RSX);
    rsxAddressToOffset(&mesh->vertices[0].nrm, &offset);
    rsxBindVertexArrayAttrib(context, GCM_VERTEX_ATTRIB_NORMAL, 0, offset,
        sizeof(S3DVertex), 3, GCM_VERTEX_DATA_TYPE_F32, GCM_LOCATION_RSX);
    rsxAddressToOffset(&mesh->vertices[0].u, &offset);
    rsxBindVertexArrayAttrib(context, GCM_VERTEX_ATTRIB_TEX0, 0, offset,
        sizeof(S3DVertex), 2, GCM_VERTEX_DATA_TYPE_F32, GCM_LOCATION_RSX);

    rsxLoadVertexProgram(context, vpo, vp_ucode);
    rsxSetVertexProgramParameter(context, vpo, projMatrix, (float*)&P);
    rsxSetVertexProgramParameter(context, vpo, mvMatrix, (float*)&modelViewMatrix);
    rsxSetFragmentProgramParameter(context, fpo, eyePosition, (float*)&objEyePos, fp_offset, GCM_LOCATION_RSX);
    rsxSetFragmentProgramParameter(context, fpo, globalAmbient, globalAmbientColor, fp_offset, GCM_LOCATION_RSX);
    rsxSetFragmentProgramParameter(context, fpo, litPosition, (float*)&objLightPos, fp_offset, GCM_LOCATION_RSX);
    rsxSetFragmentProgramParameter(context, fpo, litColor, lightColor, fp_offset, GCM_LOCATION_RSX);
    rsxSetFragmentProgramParameter(context, fpo, spec, &shininess, fp_offset, GCM_LOCATION_RSX);
    rsxSetFragmentProgramParameter(context, fpo, Kd, materialColorDiffuse, fp_offset, GCM_LOCATION_RSX);
    rsxSetFragmentProgramParameter(context, fpo, Ks, materialColorSpecular, fp_offset, GCM_LOCATION_RSX);
    rsxLoadFragmentProgramLocation(context, fpo, fp_offset, GCM_LOCATION_RSX);
    rsxSetUserClipPlaneControl(context, GCM_USER_CLIP_PLANE_DISABLE,
        GCM_USER_CLIP_PLANE_DISABLE, GCM_USER_CLIP_PLANE_DISABLE,
        GCM_USER_CLIP_PLANE_DISABLE, GCM_USER_CLIP_PLANE_DISABLE,
        GCM_USER_CLIP_PLANE_DISABLE);
    rsxAddressToOffset(&mesh->indices[0], &offset);
    rsxDrawIndexArray(context, GCM_TYPE_TRIANGLES, offset, mesh->cnt_indices,
        GCM_INDEX_TYPE_16B, GCM_LOCATION_RSX);
}

static void hitFighter(Fighter *attacker, Fighter *victim, f32 damage, f32 force)
{
    if (victim->invulnTimer > 0.0f || g_matchOver) return;
    victim->damage += damage;
    victim->vx = (f32)attacker->facing * force;
    victim->vy = force * 0.48f + 1.8f;
    victim->hitStun = 0.24f;
    victim->onGround = false;
    victim->invulnTimer = 0.10f;
    attacker->meter += 24.0f;
    if (attacker->meter > 100.0f) attacker->meter = 100.0f;
}

static void beginUltimate(int attackerIndex)
{
    if (g_ultimateTimer > 0.0f || g_matchOver) return;
    Fighter *a = &g_players[attackerIndex];
    if (a->meter < 100.0f) return;
    a->meter = 0.0f;
    g_ultimateAttacker = attackerIndex;
    g_ultimateVictim = 1 - attackerIndex;
    g_ultimateTimer = 0.92f;
    g_ultimateBannerTimer = 1.35f;
    g_ultimateHitCount = 0;
    g_players[g_ultimateVictim].shot.active = false;
}

static void updateUltimate(f32 dt)
{
    if (g_ultimateBannerTimer > 0.0f) g_ultimateBannerTimer -= dt;
    if (g_ultimateTimer <= 0.0f) return;

    Fighter *a = &g_players[g_ultimateAttacker];
    Fighter *v = &g_players[g_ultimateVictim];
    g_ultimateTimer -= dt;
    v->x = a->x + (f32)a->facing * 1.05f;
    v->y = FLOOR_Y;
    v->vx = 0.0f;
    v->vy = 0.0f;
    v->hitStun = 0.12f;
    a->attackTimer = 0.18f;

    // A short three-hit cinematic sequence, followed by a final knockback.
    f32 elapsed = 0.92f - g_ultimateTimer;
    int hitsNow = elapsed > 0.68f ? 3 : (elapsed > 0.43f ? 2 : (elapsed > 0.18f ? 1 : 0));
    while (g_ultimateHitCount < hitsNow) {
        v->damage += 9.0f;
        g_ultimateHitCount++;
    }
    if (g_ultimateTimer <= 0.0f) {
        v->damage += 14.0f;
        v->vx = (f32)a->facing * 15.0f;
        v->vy = 8.0f;
        v->hitStun = 0.65f;
        v->invulnTimer = 0.75f;
    }
}

static void updateFighter(Fighter *p, Fighter *enemy, const FighterInput &in, int index, f32 dt)
{
    bool jumpPressed = justPressed(in.jump, &p->oldJump);
    bool meleePressed = justPressed(in.melee, &p->oldMelee);
    bool rangedPressed = justPressed(in.ranged, &p->oldRanged);
    bool brutalPressed = justPressed(in.brutal, &p->oldBrutal);
    bool ultimatePressed = justPressed(in.ultimate, &p->oldUltimate);

    if (p->meleeCooldown > 0.0f) p->meleeCooldown -= dt;
    if (p->rangedCooldown > 0.0f) p->rangedCooldown -= dt;
    if (p->brutalTimer > 0.0f) p->brutalTimer -= dt;
    if (p->brutalCooldown > 0.0f) p->brutalCooldown -= dt;
    if (p->hitStun > 0.0f) p->hitStun -= dt;
    if (p->attackTimer > 0.0f) p->attackTimer -= dt;
    if (p->invulnTimer > 0.0f) p->invulnTimer -= dt;

    if (brutalPressed && p->brutalCooldown <= 0.0f) {
        p->brutalTimer = 5.0f;
        p->brutalCooldown = 13.0f;
    }
    if (ultimatePressed && p->meter >= 100.0f) beginUltimate(index);

    if (g_ultimateTimer > 0.0f) return;

    if (p->hitStun <= 0.0f) {
        if (in.left != in.right) {
            p->vx = in.left ? -5.0f : 5.0f;
            p->facing = in.left ? -1 : 1;
        } else {
            p->vx *= 0.72f;
            if (fabsf(p->vx) < 0.12f) p->vx = 0.0f;
        }
        if (jumpPressed && p->onGround) {
            p->vy = 7.8f;
            p->onGround = false;
        }
    }

    p->x += p->vx * dt;
    p->y += p->vy * dt;
    if (!p->onGround) p->vy -= 18.0f * dt;
    if (p->y <= FLOOR_Y) {
        p->y = FLOOR_Y;
        p->vy = 0.0f;
        p->onGround = true;
    }

    if (meleePressed && p->meleeCooldown <= 0.0f && p->hitStun <= 0.0f) {
        p->meleeCooldown = p->brutalTimer > 0.0f ? 0.27f : 0.40f;
        p->attackTimer = 0.22f;
        f32 dist = enemy->x - p->x;
        if ((dist * (f32)p->facing) > 0.0f && fabsf(dist) < 1.65f && fabsf(enemy->y - p->y) < 1.8f) {
            hitFighter(p, enemy, p->brutalTimer > 0.0f ? 13.0f : 7.0f,
                       p->brutalTimer > 0.0f ? 9.5f : 6.5f);
        }
    }

    if (rangedPressed && p->rangedCooldown <= 0.0f && p->hitStun <= 0.0f && !p->shot.active) {
        p->rangedCooldown = p->brutalTimer > 0.0f ? 1.15f : 2.15f;
        p->shot.active = true;
        p->shot.x = p->x + (f32)p->facing * 0.9f;
        p->shot.y = p->y + 1.55f;
        p->shot.vx = (f32)p->facing * (p->brutalTimer > 0.0f ? 12.0f : 9.0f);
        p->shot.timer = 1.8f;
    }

    if (p->x < -11.7f || p->x > 11.7f || p->y < -7.0f) {
        p->stocks--;
        p->damage = 0.0f;
        p->shot.active = false;
        p->x = index == 0 ? -3.2f : 3.2f;
        p->y = FLOOR_Y;
        p->vx = p->vy = 0.0f;
        p->invulnTimer = 1.0f;
        if (p->stocks <= 0) {
            g_matchOver = true;
            g_winner = 1 - index;
        }
    }
}

static void updateShot(Fighter *p, Fighter *enemy, f32 dt)
{
    if (!p->shot.active) return;
    p->shot.x += p->shot.vx * dt;
    p->shot.timer -= dt;
    if (p->shot.timer <= 0.0f || p->shot.x < -13.0f || p->shot.x > 13.0f) {
        p->shot.active = false;
        return;
    }
    if (fabsf(p->shot.x - enemy->x) < 0.75f && fabsf(p->shot.y - (enemy->y + 1.45f)) < 1.10f) {
        enemy->damage += 10.0f;
        enemy->vx = p->shot.vx > 0.0f ? 7.0f : -7.0f;
        enemy->vy = 3.8f;
        enemy->onGround = false;
        enemy->hitStun = 0.22f;
        enemy->invulnTimer = 0.12f;
        p->meter += 18.0f;
        if (p->meter > 100.0f) p->meter = 100.0f;
        p->shot.active = false;
    }
}

static void drawFighter(const Fighter *p, int index)
{
    f32 r = index == 0 ? 0.10f : 0.78f;
    f32 g = index == 0 ? 0.34f : 0.10f;
    f32 b = index == 0 ? 0.90f : 0.08f;
    if (p->brutalTimer > 0.0f) { r = 0.98f; g = 0.58f; b = 0.04f; }
    if (p->invulnTimer > 0.0f && ((int)(p->invulnTimer * 18.0f) % 2) == 0) return;

    drawMeshAt(mLeg, p->x - 0.18f, p->y + 0.32f, 0.05f, r * 0.8f, g * 0.8f, b * 0.8f);
    drawMeshAt(mLeg, p->x + 0.18f, p->y + 0.32f, 0.05f, r * 0.8f, g * 0.8f, b * 0.8f);
    drawMeshAt(mBody, p->x, p->y + 1.40f, 0.05f, r, g, b);
    drawMeshAt(mHead, p->x, p->y + 2.42f, 0.08f, 0.78f, 0.64f, 0.48f);

    f32 armX = p->x - (f32)p->facing * 0.47f;
    f32 leadX = p->x + (f32)p->facing * 0.47f;
    if (p->attackTimer > 0.0f) leadX += (f32)p->facing * 0.42f;
    drawMeshAt(mArm, armX, p->y + 1.45f, 0.05f, r * 0.8f, g * 0.8f, b * 0.8f);
    drawMeshAt(mArm, leadX, p->y + 1.48f, 0.14f, r, g, b);
    if (p->shot.active) drawMeshAt(mProjectile, p->shot.x, p->shot.y, 0.35f, 1.0f, 0.78f, 0.08f);
}

void drawFrame()
{
    u32 color = 0;
    setDrawEnv();
    setTexture(textureUnit->index);
    rsxSetClearColor(context, 0x00111A2C);
    rsxSetClearDepthStencil(context, 0xffffff00);
    rsxClearSurface(context, GCM_CLEAR_R | GCM_CLEAR_G | GCM_CLEAR_B | GCM_CLEAR_A | GCM_CLEAR_S | GCM_CLEAR_Z);
    rsxSetZMinMaxControl(context, GCM_FALSE, GCM_TRUE, GCM_FALSE);
    for (u32 i = 0; i < 8; ++i) rsxSetViewportClip(context, i, display_width, display_height);

    // Passing scenery and windows create the illusion of a moving train.
    for (int i = 0; i < 11; ++i) {
        f32 x = -12.0f + (f32)i * 2.4f + g_trainOffset;
        if (x > 13.0f) x -= 26.4f;
        drawMeshAt(mWindow, x, 2.20f, -4.0f, 0.07f, 0.11f, 0.18f);
        drawMeshAt(mWindow, x, 0.65f, -4.1f, 0.11f, 0.18f, 0.27f);
    }
    // Train floor, frame and rails.
    drawMeshAt(mFloor, 0.0f, -3.60f, 0.0f, 0.20f, 0.22f, 0.25f);
    drawMeshAt(mRail, 0.0f, -3.16f, 0.15f, 0.38f, 0.40f, 0.43f);
    drawMeshAt(mRail, 0.0f, -4.06f, 0.15f, 0.12f, 0.13f, 0.15f);
    for (int i = 0; i < 14; ++i) {
        f32 x = -13.0f + (f32)i * 2.0f + g_trainOffset * 1.8f;
        if (x > 14.0f) x -= 28.0f;
        drawMeshAt(mTie, x, -4.12f, 0.20f, 0.18f, 0.16f, 0.15f);
    }
    drawMeshAt(mBoundary, -11.5f, -2.85f, 0.10f, 0.55f, 0.12f, 0.10f);
    drawMeshAt(mBoundary, 11.5f, -2.85f, 0.10f, 0.55f, 0.12f, 0.10f);

    drawFighter(&g_players[0], 0);
    drawFighter(&g_players[1], 1);

    char line[160];
    DebugFont::setPosition(14, 12);
    DebugFont::setColor(0.96f, 0.96f, 0.96f, 1.0f);
    sprintf(line, "TF2 FIGHTER - TRAIN BRAWL | P1 stocks:%d dmg:%d meter:%d", g_players[0].stocks, (int)g_players[0].damage, (int)g_players[0].meter);
    DebugFont::print(line);
    DebugFont::setPosition(14, 34);
    DebugFont::setColor(1.0f, 0.66f, 0.66f, 1.0f);
    sprintf(line, "P2 stocks:%d dmg:%d meter:%d", g_players[1].stocks, (int)g_players[1].damage, (int)g_players[1].meter);
    DebugFont::print(line);
    DebugFont::setPosition(14, display_height - 42);
    DebugFont::setColor(0.86f, 0.90f, 1.0f, 1.0f);
    DebugFont::print("D-pad move | X jump | Square melee | Triangle ranged | R1 BRUTAL | Circle ultimate at 100 meter");

    if (g_players[0].brutalTimer > 0.0f || g_players[1].brutalTimer > 0.0f) {
        DebugFont::setPosition((s32)(display_width / 2 - 50), 62);
        DebugFont::setColor(1.0f, 0.62f, 0.08f, 1.0f);
        DebugFont::print("BRUTAL MODE!");
    }
    if (g_ultimateBannerTimer > 0.0f) {
        DebugFont::setPosition((s32)(display_width / 2 - 85), (s32)(display_height / 2 - 18));
        DebugFont::setColor(1.0f, 0.20f, 0.06f, 1.0f);
        DebugFont::print("POOTIS ENGAGE!!");
    }
    if (g_matchOver) {
        DebugFont::setPosition((s32)(display_width / 2 - 80), (s32)(display_height / 2 + 18));
        DebugFont::setColor(1.0f, 1.0f, 0.45f, 1.0f);
        DebugFont::print(g_winner == 0 ? "PLAYER 1 WINS - press START" : "PLAYER 2 WINS - press START");
    }
}

int main(int argc, const char *argv[])
{
    padInfo padinfo;
    padData paddata[MAX_PADS];
    void *host_addr = memalign(HOST_ADDR_ALIGNMENT, HOSTBUFFER_SIZE);
    printf("TF2 Fighter prototype booting...\n");

    eye_pos = Point3(0.0f, 0.0f, 22.0f);
    eye_dir = Point3(0.0f, 0.0f, 0.0f);
    up_vec = Vector3(0.0f, 1.0f, 0.0f);
    init_screen(host_addr, HOSTBUFFER_SIZE);
    ioPadInit(7);
    init_shader();
    init_texture();
    DebugFont::init();
    DebugFont::setScreenRes(display_width, display_height);

    mFloor = makeBox(24.0f, 0.70f, 1.1f);
    mTie = makeBox(1.15f, 0.16f, 0.40f);
    mRail = makeBox(24.0f, 0.10f, 0.18f);
    mWindow = makeBox(2.05f, 1.25f, 0.14f);
    mBody = makeBox(0.66f, 1.20f, 0.52f);
    mHead = makeBox(0.62f, 0.66f, 0.58f);
    mArm = makeBox(0.24f, 0.72f, 0.30f);
    mLeg = makeBox(0.27f, 0.62f, 0.34f);
    mProjectile = makeBox(0.34f, 0.34f, 0.34f);
    mBoundary = makeBox(0.16f, 0.78f, 0.55f);
    resetFighter(&g_players[0], -3.1f, 1);
    resetFighter(&g_players[1], 3.1f, -1);

    atexit(program_exit_callback);
    sysUtilRegisterCallback(0, sysutil_exit_callback, NULL);
    P = transpose(Matrix4::perspective(DEGTORAD(45.0f), aspect_ratio, 1.0f, 3000.0f));
    setDrawEnv();
    setRenderTarget(curr_fb);
    running = 1;

    while (running) {
        sysUtilCheckCallback();
        memset(&paddata, 0, sizeof(paddata));
        ioPadGetInfo(&padinfo);
        bool connected[MAX_PADS];
        for (int i = 0; i < MAX_PADS; ++i) {
            connected[i] = padinfo.status[i] != 0;
            if (connected[i]) ioPadGetData(i, &paddata[i]);
        }
        FighterInput in0 = readInput(&paddata[0], connected[0]);
        FighterInput in1;
        if (MAX_PADS > 1) in1 = readInput(&paddata[1], connected[1]);
        else memset(&in1, 0, sizeof(in1));

        // START restarts a finished match.
        if (g_matchOver && ((connected[0] && paddata[0].BTN_START) ||
                            (MAX_PADS > 1 && connected[1] && paddata[1].BTN_START))) {
            resetFighter(&g_players[0], -3.1f, 1);
            resetFighter(&g_players[1], 3.1f, -1);
            g_matchOver = false;
            g_ultimateTimer = g_ultimateBannerTimer = 0.0f;
        }

        const f32 dt = 1.0f / 60.0f;
        g_trainOffset += 0.12f;
        if (g_trainOffset >= 2.0f) g_trainOffset -= 2.0f;
        updateUltimate(dt);
        if (!g_matchOver) {
            updateFighter(&g_players[0], &g_players[1], in0, 0, dt);
            updateFighter(&g_players[1], &g_players[0], in1, 1, dt);
            updateShot(&g_players[0], &g_players[1], dt);
            updateShot(&g_players[1], &g_players[0], dt);
        }
        drawFrame();
        flip();
    }

    DebugFont::shutdown();
    program_exit_callback();
    return 0;
}
'''
main_cpp.write_text(source[:idx] + game_code, encoding="utf-8")

mk = makefile.read_text(encoding="utf-8")
mk, n_title = re.subn(r"(?m)^\s*TITLE\s*=.*$", "TITLE = TF2 Fighter Prototype", mk, count=1)
mk, n_appid = re.subn(r"(?m)^\s*APPID\s*=.*$", "APPID = TF2F00001", mk, count=1)
if n_title != 1 or n_appid != 1:
    raise SystemExit("Could not safely update TITLE and APPID in the upstream Makefile.")
makefile.write_text(mk, encoding="utf-8")
print("Patched rsxtest into TF2 Fighter prototype.")
